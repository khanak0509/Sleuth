from __future__ import annotations

import contextvars
import functools
import json
import math
import os
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tracers.context import register_configure_hook


DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "text-embedding-3-small": (0.02, 0.0),
}


def load_pricing() -> dict[str, tuple[float, float]]:
    pricing = dict(DEFAULT_PRICING)
    raw = os.getenv("LLM_PRICING_JSON")
    if raw:
        try:
            for k, v in json.loads(raw).items():
                pricing[k] = (float(v[0]), float(v[1]))
        except (ValueError, TypeError, IndexError):
            pass
    return pricing


PRICING = load_pricing()


def price_for(model: str | None) -> tuple[float, float] | None:
    if not model:
        return None
    best = None
    for name in PRICING:
        if model.startswith(name) and (best is None or len(name) > len(best)):
            best = name
    return PRICING[best] if best else None


def cost_usd(model: str | None, input_tokens: int, output_tokens: int) -> float:
    p = price_for(model)
    if p is None:
        return 0.0
    return (input_tokens * p[0] + output_tokens * p[1]) / 1_000_000


@dataclass
class Span:
    name: str
    kind: str
    start_ms: float
    duration_ms: float
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None


@dataclass
class RequestTrace:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    cloud_trace_id: str | None = None
    path: str | None = None
    error: str | None = None
    spans: list[Span] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter)
    _t_end: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def offset_ms(self, t: float) -> float:
        return (t - self._t0) * 1000

    def add(self, span: Span) -> None:
        with self._lock:
            self.spans.append(span)

    def finish(self) -> None:
        if self._t_end is None:
            self._t_end = time.perf_counter()

    @property
    def total_ms(self) -> float:
        end = self._t_end if self._t_end is not None else time.perf_counter()
        return (end - self._t0) * 1000

    def summary(self) -> dict[str, Any]:
        llm = [s for s in self.spans if s.kind == "llm"]
        in_tok = sum(s.input_tokens for s in llm)
        out_tok = sum(s.output_tokens for s in llm)
        llm_ms = sum(s.duration_ms for s in llm)

        stages: dict[str, dict[str, Any]] = {}
        for s in self.spans:
            st = stages.setdefault(
                s.name, {"ms": 0.0, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            )
            if s.kind == "stage":
                st["ms"] += s.duration_ms
            else:
                st["llm_calls"] += 1
                st["input_tokens"] += s.input_tokens
                st["output_tokens"] += s.output_tokens
                st["cost_usd"] += s.cost_usd
        for st in stages.values():
            st["ms"] = round(st["ms"], 1)
            st["cost_usd"] = round(st["cost_usd"], 8)

        return {
            "request_id": self.request_id,
            "path": self.path,
            "error": self.error,
            "latency_ms": round(self.total_ms, 1),
            "llm_calls": len(llm),
            "llm_errors": sum(1 for s in llm if s.error),
            "llm_ms": round(llm_ms, 1),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
            "cost_usd": round(sum(s.cost_usd for s in llm), 8),
            "output_tokens_per_sec": round(out_tok / (llm_ms / 1000), 1) if llm_ms > 0 else 0.0,
            "stages": stages,
        }


_trace_var: contextvars.ContextVar[RequestTrace | None] = contextvars.ContextVar("sleuth_trace", default=None)
_stage_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("sleuth_stage", default=None)


def current_trace() -> RequestTrace | None:
    return _trace_var.get()


def _model_from_kwargs(kwargs: dict, serialized: dict | None) -> str | None:
    inv = kwargs.get("invocation_params") or {}
    model = inv.get("model") or inv.get("model_name")
    if not model and serialized:
        sk = serialized.get("kwargs") or {}
        model = sk.get("model") or sk.get("model_name")
    return model


def _usage_from_result(response) -> tuple[int, int, str | None]:
    in_tok = out_tok = 0
    model = None
    for gens in response.generations or []:
        for g in gens:
            msg = getattr(g, "message", None)
            um = getattr(msg, "usage_metadata", None)
            if um:
                in_tok += int(um.get("input_tokens", 0) or 0)
                out_tok += int(um.get("output_tokens", 0) or 0)
            model = model or (getattr(msg, "response_metadata", None) or {}).get("model_name")
    llm_output = response.llm_output or {}
    if not (in_tok or out_tok):
        tu = llm_output.get("token_usage") or {}
        in_tok = int(tu.get("prompt_tokens", 0) or 0)
        out_tok = int(tu.get("completion_tokens", 0) or 0)
    return in_tok, out_tok, model or llm_output.get("model_name")


class TelemetryCallbackHandler(BaseCallbackHandler):
    raise_error = False

    def __init__(self) -> None:
        self._open: dict[Any, tuple[float, str, str | None, RequestTrace]] = {}
        self._lock = threading.Lock()

    def _start(self, run_id, serialized, metadata, kwargs) -> None:
        tr = _trace_var.get()
        if tr is None:
            return
        stage = _stage_var.get() or (metadata or {}).get("langgraph_node") or "unattributed"
        with self._lock:
            self._open[run_id] = (time.perf_counter(), stage, _model_from_kwargs(kwargs, serialized), tr)

    def on_chat_model_start(
        self, serialized, messages, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs
    ):
        self._start(run_id, serialized, metadata, kwargs)

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        self._start(run_id, serialized, metadata, kwargs)

    def _pop(self, run_id):
        with self._lock:
            return self._open.pop(run_id, None)

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        opened = self._pop(run_id)
        if opened is None:
            return
        t_start, stage, model, tr = opened
        t_end = time.perf_counter()
        in_tok, out_tok, resp_model = _usage_from_result(response)
        model = resp_model or model
        tr.add(
            Span(
                name=stage,
                kind="llm",
                start_ms=round(tr.offset_ms(t_start), 1),
                duration_ms=round((t_end - t_start) * 1000, 1),
                model=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost_usd(model, in_tok, out_tok),
            )
        )

    def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        opened = self._pop(run_id)
        if opened is None:
            return
        t_start, stage, model, tr = opened
        tr.add(
            Span(
                name=stage,
                kind="llm",
                start_ms=round(tr.offset_ms(t_start), 1),
                duration_ms=round((time.perf_counter() - t_start) * 1000, 1),
                model=model,
                error=f"{type(error).__name__}: {error}"[:300],
            )
        )


HANDLER = TelemetryCallbackHandler()
_handler_var: contextvars.ContextVar[BaseCallbackHandler | None] = contextvars.ContextVar(
    "sleuth_telemetry_handler", default=None
)
register_configure_hook(_handler_var, inheritable=True)


@contextmanager
def stage(name: str) -> Iterator[None]:
    tr = _trace_var.get()
    token = _stage_var.set(name)
    t0 = time.perf_counter()
    try:
        yield
    finally:
        _stage_var.reset(token)
        if tr is not None:
            tr.add(
                Span(
                    name=name,
                    kind="stage",
                    start_ms=round(tr.offset_ms(t0), 1),
                    duration_ms=round((time.perf_counter() - t0) * 1000, 1),
                )
            )


def timed(name: str):

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with stage(name):
                return fn(*args, **kwargs)

        return wrapper

    return deco


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, math.ceil(p / 100 * len(s)) - 1))
    return s[k]


class MetricsStore:
    def __init__(self, maxlen: int = 1000) -> None:
        self._rows: deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self.started_at = time.time()

    def record(self, summary: dict) -> None:
        with self._lock:
            self._rows.append(summary)

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._rows)
        n = len(rows)
        if n == 0:
            return {"requests": 0}

        lat = [r["latency_ms"] for r in rows]
        cost = [r["cost_usd"] for r in rows]
        toks = [r["total_tokens"] for r in rows]
        out_tok = sum(r["output_tokens"] for r in rows)
        llm_ms = sum(r["llm_ms"] for r in rows)

        stage_ms: dict[str, list[float]] = {}
        stage_cost: dict[str, float] = {}
        stage_tokens: dict[str, int] = {}
        for r in rows:
            for name, st in r["stages"].items():
                if st["ms"] > 0:
                    stage_ms.setdefault(name, []).append(st["ms"])
                stage_cost[name] = stage_cost.get(name, 0.0) + st["cost_usd"]
                stage_tokens[name] = stage_tokens.get(name, 0) + st["input_tokens"] + st["output_tokens"]

        paths: dict[str, int] = {}
        for r in rows:
            key = r.get("path") or "unknown"
            paths[key] = paths.get(key, 0) + 1

        total_cost = sum(cost)
        return {
            "requests": n,
            "errors": sum(1 for r in rows if r.get("error")),
            "latency_ms": {
                "p50": round(percentile(lat, 50), 1),
                "p95": round(percentile(lat, 95), 1),
                "p99": round(percentile(lat, 99), 1),
                "mean": round(sum(lat) / n, 1),
            },
            "cost_per_request_usd": {
                "mean": round(total_cost / n, 6),
                "p95": round(percentile(cost, 95), 6),
                "total": round(total_cost, 6),
            },
            "tokens_per_request": {"mean": round(sum(toks) / n, 1), "p95": percentile(toks, 95)},
            "llm_calls_per_request": round(sum(r["llm_calls"] for r in rows) / n, 2),
            "output_tokens_per_sec": round(out_tok / (llm_ms / 1000), 1) if llm_ms > 0 else 0.0,
            "paths": paths,
            "stages": {
                name: {
                    "p50_ms": round(percentile(v, 50), 1),
                    "p95_ms": round(percentile(v, 95), 1),
                    "cost_share": round(stage_cost.get(name, 0.0) / total_cost, 3) if total_cost else 0.0,
                    "tokens": stage_tokens.get(name, 0),
                }
                for name, v in sorted(stage_ms.items())
            },
            "window_started_at": self.started_at,
        }


METRICS = MetricsStore(maxlen=int(os.getenv("METRICS_WINDOW", "1000")))


def parse_trace_header(headers) -> str | None:
    tp = headers.get("traceparent")
    if tp:
        parts = tp.split("-")
        if len(parts) >= 2 and len(parts[1]) == 32:
            return parts[1]
    xc = headers.get("x-cloud-trace-context")
    if xc:
        tid = xc.split("/")[0].strip()
        if tid:
            return tid
    return None


def log_trace(tr: RequestTrace, summary: dict) -> None:
    entry: dict[str, Any] = {
        "severity": "ERROR" if summary.get("error") else "INFO",
        "message": f"incident request {summary['request_id']} path={summary['path']} "
        f"latency_ms={summary['latency_ms']} cost_usd={summary['cost_usd']}",
        "event": "llm_request",
        **summary,
        "spans": [asdict(s) for s in sorted(tr.spans, key=lambda s: s.start_ms)],
    }
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if project and tr.cloud_trace_id:
        entry["logging.googleapis.com/trace"] = f"projects/{project}/traces/{tr.cloud_trace_id}"
    print(json.dumps(entry, default=str), flush=True)


@contextmanager
def request_trace(cloud_trace_id: str | None = None, store: MetricsStore | None = None, log: bool = True):
    tr = RequestTrace(cloud_trace_id=cloud_trace_id)
    t_token = _trace_var.set(tr)
    h_token = _handler_var.set(HANDLER)
    try:
        yield tr
    except Exception as e:
        tr.error = f"{type(e).__name__}: {e}"[:300]
        raise
    finally:
        _handler_var.reset(h_token)
        _trace_var.reset(t_token)
        tr.finish()
        summary = tr.summary()
        (store or METRICS).record(summary)
        if log:
            try:
                log_trace(tr, summary)
            except Exception:
                pass
