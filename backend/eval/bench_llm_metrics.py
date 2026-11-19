import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).parent
TESTSETS = ROOT / "testsets"


def pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    import math

    return s[max(0, min(len(s) - 1, math.ceil(p / 100 * len(s)) - 1))]


def load_queries(limit):
    qs = [r["query"] for r in json.loads((TESTSETS / "retrieval.json").read_text())]
    qs += [r["query"] for r in json.loads((TESTSETS / "fallback.json").read_text())]
    guards = json.loads((TESTSETS / "guardrails.json").read_text())["input"]
    qs += [r["query"] for r in guards if r.get("should_block")][:3]
    return qs[:limit] if limit else qs


def wait_ready(c, timeout):
    t0 = time.time()
    first = None
    while time.time() - t0 < timeout:
        try:
            r = c.get("/stream/status")
            if first is None:
                first = time.time() - t0
            if r.status_code == 200 and r.json().get("event_count", 0) > 0:
                return first, time.time() - t0
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise SystemExit(f"service not ready after {timeout}s (no indexed events)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--token", default=None, help="optional bearer token")
    ap.add_argument("--label", default="local")
    ap.add_argument("--limit", type=int, default=0, help="max queries (0 = all)")
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--ready-timeout", type=int, default=300)
    args = ap.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    queries = load_queries(args.limit) * args.repeat

    with httpx.Client(base_url=args.url.rstrip("/"), headers=headers, timeout=180) as c:
        first_response_s, ready_s = wait_ready(c, args.ready_timeout)

        c.post("/incident", json={"query": "warmup: any recent PushEvent activity?"})

        def one(q):
            t0 = time.perf_counter()
            try:
                r = c.post("/incident", json={"query": q})
                ok = r.status_code == 200
                body = r.json() if ok else {}
            except httpx.HTTPError as e:
                ok, body = False, {"error": str(e)}
            return {
                "query": q,
                "ok": ok,
                "client_ms": (time.perf_counter() - t0) * 1000,
                "path": body.get("path_taken"),
                "metrics": body.get("metrics") or {},
            }

        t_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            rows = list(ex.map(one, queries))
        wall_s = time.perf_counter() - t_start

        server = c.get("/metrics/llm").json()

    good = [r for r in rows if r["ok"] and r["metrics"]]
    lat = [r["client_ms"] for r in good]
    cost = [r["metrics"]["cost_usd"] for r in good]
    toks = [r["metrics"]["input_tokens"] + r["metrics"]["output_tokens"] for r in good]
    tps = [r["metrics"]["output_tokens_per_sec"] for r in good if r["metrics"]["output_tokens_per_sec"]]
    paths = {}
    for r in good:
        paths[r["path"]] = paths.get(r["path"], 0) + 1

    out = {
        "label": args.label,
        "url": args.url,
        "requests": len(rows),
        "success_rate": round(len(good) / len(rows), 3) if rows else 0,
        "concurrency": args.concurrency,
        "throughput_rps": round(len(rows) / wall_s, 3) if wall_s else 0,
        "client_latency_ms": {
            "p50": round(pct(lat, 50), 1),
            "p95": round(pct(lat, 95), 1),
            "mean": round(statistics.mean(lat), 1) if lat else 0,
        },
        "cost_per_request_usd": {
            "mean": round(statistics.mean(cost), 6) if cost else 0,
            "p95": round(pct(cost, 95), 6),
            "per_1k_requests": round(statistics.mean(cost) * 1000, 3) if cost else 0,
        },
        "tokens_per_request_mean": round(statistics.mean(toks), 1) if toks else 0,
        "output_tokens_per_sec_median": round(statistics.median(tps), 1) if tps else 0,
        "paths": paths,
        "cold_start": {"first_response_s": round(first_response_s, 1), "index_warm_s": round(ready_s, 1)},
        "server_snapshot": server,
    }

    (ROOT / f"metrics_llm_{args.label}.json").write_text(json.dumps(out, indent=2))

    lines = [
        f"# LLM serving metrics: {args.label}",
        "",
        f"Target: `{args.url}`, {len(rows)} requests, concurrency {args.concurrency}. "
        "Warmup excluded from client stats.",
        "",
        "| metric | value |",
        "|---|---|",
        f"| success rate | {out['success_rate']:.1%} |",
        f"| latency p50 / p95 (client) | {out['client_latency_ms']['p50'] / 1000:.2f}s / "
        f"{out['client_latency_ms']['p95'] / 1000:.2f}s |",
        f"| cost per request mean / p95 | ${out['cost_per_request_usd']['mean']:.5f} / "
        f"${out['cost_per_request_usd']['p95']:.5f} |",
        f"| cost per 1k requests | ${out['cost_per_request_usd']['per_1k_requests']:.2f} |",
        f"| tokens per request (mean) | {out['tokens_per_request_mean']:.0f} |",
        f"| output tokens/sec (median) | {out['output_tokens_per_sec_median']:.1f} |",
        f"| LLM calls per request | {server.get('llm_calls_per_request', 0)} |",
        f"| throughput | {out['throughput_rps']:.2f} req/s |",
        f"| cold start: first response / index warm | {first_response_s:.1f}s / {ready_s:.1f}s |",
        f"| paths | {', '.join(f'{k}={v}' for k, v in sorted(paths.items(), key=lambda kv: str(kv[0])))} |",
        "",
        "## Per-stage (server side)",
        "",
        "| stage | p50 | p95 | share of LLM cost | tokens |",
        "|---|---|---|---|---|",
    ]
    for name, st in (server.get("stages") or {}).items():
        lines.append(
            f"| {name} | {st['p50_ms']:.0f} ms | {st['p95_ms']:.0f} ms | {st['cost_share']:.0%} | {st['tokens']} |"
        )
    (ROOT / f"results_llm_{args.label}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
