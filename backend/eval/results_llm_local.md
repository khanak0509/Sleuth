# LLM serving metrics: local

Target: `http://127.0.0.1:8000`, 50 requests, concurrency 1. Warmup excluded from client stats.

| metric | value |
|---|---|
| success rate | 100.0% |
| latency p50 / p95 (client) | 7.76s / 15.57s |
| cost per request mean / p95 | $0.00033 / $0.00057 |
| cost per 1k requests | $0.33 |
| tokens per request (mean) | 1587 |
| output tokens/sec (median) | 29.9 |
| LLM calls per request | 5.12 |
| throughput | 0.13 req/s |
| cold start: first response / index warm | 2.0s / 4.0s |
| paths | direct=32, fallback=9, rejected=9 |

## Per-stage (server side)

| stage | p50 | p95 | share of LLM cost | tokens |
|---|---|---|---|---|
| answer | 1857 ms | 3268 ms | 19% | 11705 |
| fallback | 8497 ms | 14058 ms | 12% | 5606 |
| grade | 1240 ms | 1585 ms | 17% | 13704 |
| input_guardrail | 1149 ms | 1527 ms | 14% | 10814 |
| output_guardrail | 900 ms | 1215 ms | 16% | 17290 |
| pick_tool | 882 ms | 1554 ms | 16% | 17508 |
| retrieve | 621 ms | 1157 ms | 0% | 0 |
| rewrite_query | 888 ms | 1188 ms | 6% | 5493 |
