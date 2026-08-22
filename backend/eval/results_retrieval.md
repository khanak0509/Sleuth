# Retrieval eval

- cases: 32
- Recall@3: **1.000**
- Recall@5: **1.000**
- Precision@5 (mean): **0.362**
- stale (shopify/hydrogen before ingest): hit=False recall=0.000
- fresh (after ingest) Recall@3: hit=True recall=1.000

| # | query | hit@3 | hit@5 | P@5 |
|---|---|---|---|---|
| 1 | workflow failures in microsoft/vscode | True | True | 0.40 |
| 2 | push events to kubernetes/kubernetes | True | True | 0.20 |
| 3 | new issues opened on facebook/react | True | True | 0.60 |
| 4 | pull requests merged in rust-lang/rust | True | True | 0.40 |
| 5 | failed CI runs for tensorflow/tensorflow | True | True | 0.40 |
| 6 | who starred golang/go recently | True | True | 0.20 |
| 7 | fork activity on torvalds/linux | True | True | 0.20 |
| 8 | release tags published by nodejs/node | True | True | 0.20 |
| 9 | branch create events in apache/spark | True | True | 0.20 |
| 10 | issue storms on angular/angular | True | True | 0.60 |
| 11 | PR activity in pytorch/pytorch | True | True | 0.40 |
| 12 | pushes to homebrew/brew | True | True | 0.20 |
| 13 | workflow conclusions for actions/runner | True | True | 0.20 |
| 14 | delete branch events in elastic/elasticsearch | True | True | 0.20 |
| 15 | watchers starring vercel/next.js | True | True | 0.20 |
| 16 | CI failure burst on hashicorp/terraform | True | True | 0.40 |
| 17 | issue titled memory leak in denoland/deno | True | True | 0.40 |
| 18 | merged PR in django/django | True | True | 0.20 |
| 19 | push commits to redis/redis | True | True | 0.20 |
| 20 | workflow run failure conclusion=failure for graf | True | True | 0.40 |
| 21 | which project had a CI workflow named build that | True | True | 0.40 |
| 22 | failed test workflow conclusion among grafana vs | True | True | 0.40 |
| 23 | concurrent mode state bug opened on the React tr | True | True | 0.60 |
| 24 | zone.js change-detection issue opened on Angular | True | True | 0.60 |
| 25 | memory leak in fetch reported against Deno | True | True | 0.40 |
| 26 | memory leak in http client reported against Node | True | True | 0.20 |
| 27 | state management race in useEffect hooks | True | True | 0.60 |
| 28 | state management bug in Angular signals | True | True | 0.60 |
| 29 | IaC provider CI build job concluded failure | True | True | 0.40 |
| 30 | dashboard observability test workflow concluded  | True | True | 0.40 |
| 31 | AMP training fix pull request opened on PyTorch | True | True | 0.40 |
| 32 | language feature stabilize PR closed and merged  | True | True | 0.40 |
