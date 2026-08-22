# Grading eval

- cases: 34
- accuracy: **0.912**
- false-positive rate (pred relevant when not): **0.125**  ← dangerous failure
- confusion: tp=10 fp=3 tn=21 fn=0

| # | query | gold | pred | ok |
|---|---|---|---|---|
| 1 | Why are workflows failing on microsoft/v | True | True | True |
| 2 | Push activity on kubernetes/kubernetes | True | True | True |
| 3 | Issues opened against facebook/react | True | True | True |
| 4 | CI failures for tensorflow/tensorflow | False | False | True |
| 5 | Release published by nodejs/node | True | True | True |
| 6 | Workflow failures on grafana/grafana | False | False | True |
| 7 | PR merges in rust-lang/rust | True | True | True |
| 8 | Who starred golang/go? | False | False | True |
| 9 | Fork of torvalds/linux | True | True | True |
| 10 | Delete branch events in elastic/elastics | False | False | True |
| 11 | Memory leak issue on denoland/deno | True | True | True |
| 12 | Burst of failures on hashicorp/terraform | True | True | True |
| 13 | Pushes to homebrew/brew | False | False | True |
| 14 | django/django pull request activity | True | True | True |
| 15 | actions/runner workflow status | True | True | True |
| 16 | What broke in pytorch/pytorch CI? | False | False | True |
| 17 | Was the memory leak issue on denoland/de | False | False | True |
| 18 | Did elastic/elasticsearch delete the rel | False | False | True |
| 19 | Any WorkflowRunEvent failure named build | False | False | True |
| 20 | Is there a merged Stabilize PR on rust-l | False | False | True |
| 21 | Who forked torvalds/linux as contrib/lin | False | False | True |
| 22 | Push to kubernetes/kubernetes fixing fla | False | False | True |
| 23 | nodejs/node release for tag v22.0.0 publ | False | False | True |
| 24 | CI failure conclusion on microsoft/vscod | False | False | True |
| 25 | Any open issue about concurrent mode / s | False | False | True |
| 26 | Memory leak in Deno fetch specifically? | False | True | False |
| 27 | Did terraform's build workflow fail? | False | False | True |
| 28 | AMP fix PR activity on pytorch/pytorch? | False | False | True |
| 29 | State management bug opened against Angu | False | False | True |
| 30 | Node http-client memory leak issue open? | False | True | False |
| 31 | Grafana test workflow failure in the log | False | False | True |
| 32 | Stabilize feature merged on rust-lang/ru | False | False | True |
| 33 | App-router fetch memory leak on next.js? | False | True | False |
| 34 | zone.js issue storm on angular/angular? | False | False | True |
