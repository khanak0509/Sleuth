from typing import TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

import telemetry
from telemetry import (
    MetricsStore,
    cost_usd,
    parse_trace_header,
    percentile,
    request_trace,
    stage,
    timed,
)


def fake_llm(n_calls: int, in_tok: int = 100, out_tok: int = 20, model: str = "gpt-4o-mini-2024-07-18"):
    msgs = [
        AIMessage(
            content="ok",
            usage_metadata={"input_tokens": in_tok, "output_tokens": out_tok, "total_tokens": in_tok + out_tok},
            response_metadata={"model_name": model},
        )
        for _ in range(n_calls)
    ]
    return GenericFakeChatModel(messages=iter(msgs))


class S(TypedDict):
    x: str


def build_graph(llm):
    def a(state):
        llm.invoke("hi")
        return {"x": "a"}

    def b(state):
        llm.invoke("hi")
        return {"x": "b"}

    g = StateGraph(S)
    g.add_node("node_a", timed("node_a")(a))
    g.add_node("node_b", timed("node_b")(b))
    g.set_entry_point("node_a")
    g.add_edge("node_a", "node_b")
    g.add_edge("node_b", END)
    return g.compile()


def test_cost_prefix_match():
    assert cost_usd("gpt-4o-mini-2024-07-18", 1_000_000, 0) == pytest.approx(0.15)
    assert cost_usd("gpt-4o-mini", 0, 1_000_000) == pytest.approx(0.60)
    assert cost_usd("gpt-4o-2024-08-06", 1_000_000, 0) == pytest.approx(2.50)
    assert cost_usd("unknown-model", 1000, 1000) == 0.0


def test_percentile_nearest_rank():
    v = list(range(1, 21))
    assert percentile(v, 50) == 10
    assert percentile(v, 95) == 19
    assert percentile(v, 100) == 20
    assert percentile([], 95) == 0.0


def test_trace_counts_each_llm_call_once_and_attributes_stages():
    store = MetricsStore()
    llm = fake_llm(3)
    graph = build_graph(llm)

    with request_trace(store=store, log=False) as tr:
        with stage("guard"):
            llm.invoke("check")
        graph.invoke({"x": ""})
        tr.path = "direct"

    s = tr.summary()
    assert s["llm_calls"] == 3
    assert s["input_tokens"] == 300
    assert s["output_tokens"] == 60
    assert s["cost_usd"] == pytest.approx(3 * (100 * 0.15 + 20 * 0.60) / 1e6)
    assert set(s["stages"]) == {"guard", "node_a", "node_b"}
    for name in ("guard", "node_a", "node_b"):
        assert s["stages"][name]["llm_calls"] == 1
    assert s["path"] == "direct"
    assert store.snapshot()["requests"] == 1


def test_no_recording_outside_a_trace():
    store = MetricsStore()
    llm = fake_llm(1)
    llm.invoke("no trace active")
    assert store.snapshot() == {"requests": 0}
    assert telemetry.current_trace() is None


def test_error_is_recorded_and_reraised():
    store = MetricsStore()
    with pytest.raises(RuntimeError):
        with request_trace(store=store, log=False):
            raise RuntimeError("boom")
    snap = store.snapshot()
    assert snap["requests"] == 1 and snap["errors"] == 1


def test_snapshot_aggregates():
    store = MetricsStore()
    for i in range(1, 11):
        llm = fake_llm(1, in_tok=1000 * i, out_tok=100)
        with request_trace(store=store, log=False) as tr:
            with stage("answer"):
                llm.invoke("q")
            tr.path = "fallback" if i % 5 == 0 else "direct"
    snap = store.snapshot()
    assert snap["requests"] == 10
    assert snap["paths"] == {"direct": 8, "fallback": 2}
    assert snap["llm_calls_per_request"] == 1
    assert snap["tokens_per_request"]["mean"] == pytest.approx(5500 + 100)
    assert snap["stages"]["answer"]["cost_share"] == pytest.approx(1.0)
    assert snap["cost_per_request_usd"]["p95"] >= snap["cost_per_request_usd"]["mean"]


def test_log_line_has_cloud_trace_field(capsys, monkeypatch):
    import json

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-proj")
    with request_trace(cloud_trace_id="abc123", store=MetricsStore()) as tr:
        tr.path = "rejected"
    line = capsys.readouterr().out.strip().splitlines()[-1]
    entry = json.loads(line)
    assert entry["logging.googleapis.com/trace"] == "projects/demo-proj/traces/abc123"
    assert entry["severity"] == "INFO"
    assert entry["path"] == "rejected"


def test_parse_trace_header():
    tid = "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parse_trace_header({"traceparent": f"00-{tid}-00f067aa0ba902b7-01"}) == tid
    assert parse_trace_header({"x-cloud-trace-context": "105445aa7843bc8bf206b120001000/1;o=1"}) == (
        "105445aa7843bc8bf206b120001000"
    )
    assert parse_trace_header({}) is None
