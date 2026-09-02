# Retrieval eval

- cases: 32 (+ 5 vague rewrite cases)
- Recall@3: **1.000**
- Recall@5: **1.000**
- Precision@5 dense-only (before): **0.362**
- Precision@5 hybrid+filter+rerank (after): **0.875**
- delta P@5: **+0.512**
- stale (shopify/hydrogen before ingest): hit=False recall=0.000
- fresh (after ingest) Recall@3: hit=True recall=1.000

## Hybrid vs dense Precision@5

| # | query | hit@3 | hit@5 | P@5 dense | P@5 hybrid |
|---|---|---|---|---|---|
| 1 | workflow failures in microsoft/vscode | True | True | 0.40 | 1.00 |
| 2 | push events to kubernetes/kubernetes | True | True | 0.20 | 1.00 |
| 3 | new issues opened on facebook/react | True | True | 0.60 | 1.00 |
| 4 | pull requests merged in rust-lang/rust | True | True | 0.40 | 1.00 |
| 5 | failed CI runs for tensorflow/tensorflow | True | True | 0.40 | 1.00 |
| 6 | who starred golang/go recently | True | True | 0.20 | 1.00 |
| 7 | fork activity on torvalds/linux | True | True | 0.20 | 1.00 |
| 8 | release tags published by nodejs/node | True | True | 0.20 | 1.00 |
| 9 | branch create events in apache/spark | True | True | 0.20 | 1.00 |
| 10 | issue storms on angular/angular | True | True | 0.60 | 1.00 |
| 11 | PR activity in pytorch/pytorch | True | True | 0.40 | 1.00 |
| 12 | pushes to homebrew/brew | True | True | 0.20 | 1.00 |
| 13 | workflow conclusions for actions/runner | True | True | 0.20 | 1.00 |
| 14 | delete branch events in elastic/elastics | True | True | 0.20 | 1.00 |
| 15 | watchers starring vercel/next.js | True | True | 0.20 | 0.50 |
| 16 | CI failure burst on hashicorp/terraform | True | True | 0.40 | 1.00 |
| 17 | issue titled memory leak in denoland/den | True | True | 0.40 | 1.00 |
| 18 | merged PR in django/django | True | True | 0.20 | 1.00 |
| 19 | push commits to redis/redis | True | True | 0.20 | 1.00 |
| 20 | workflow run failure conclusion=failure  | True | True | 0.40 | 1.00 |
| 21 | which project had a CI workflow named bu | True | True | 0.40 | 0.40 |
| 22 | failed test workflow conclusion among gr | True | True | 0.40 | 0.40 |
| 23 | concurrent mode state bug opened on the  | True | True | 0.60 | 1.00 |
| 24 | zone.js change-detection issue opened on | True | True | 0.60 | 1.00 |
| 25 | memory leak in fetch reported against De | True | True | 0.40 | 1.00 |
| 26 | memory leak in http client reported agai | True | True | 0.20 | 0.50 |
| 27 | state management race in useEffect hooks | True | True | 0.60 | 0.40 |
| 28 | state management bug in Angular signals | True | True | 0.60 | 1.00 |
| 29 | IaC provider CI build job concluded fail | True | True | 0.40 | 0.40 |
| 30 | dashboard observability test workflow co | True | True | 0.40 | 0.40 |
| 31 | AMP training fix pull request opened on  | True | True | 0.40 | 1.00 |
| 32 | language feature stabilize PR closed and | True | True | 0.40 | 1.00 |

## Query rewrite (vague cases)

- Recall@3 raw: **0.800**
- Recall@3 rewritten: **1.000**
- delta: **+0.200**

| # | raw query | rewritten | hit@3 raw | hit@3 rewritten |
|---|---|---|---|---|
| 1 | vs code ci brokne again | microsoft/vscode WorkflowRunEvent fa | True | True |
| 2 | something weird with reakt issues la | IssuesEvent in facebook/react has be | False | True |
| 3 | memry leak fetch on that deno runtim | memory leak issue in denoland/deno | True | True |
| 4 | hashi form build keep failing | hashicorp/terraform WorkflowRunEvent | True | True |
| 5 | grafna tests went red again | grafana/grafana tests failed again | True | True |
