# Faithfulness eval

- cases: 8
- mean faithful_score on expect_faithful=true: **5.00**
- mean including planted hallucinations: **3.75**
- answers scoring <=2 (manual review): 2

| # | score | expect_faithful | unsupported | query |
|---|---|---|---|---|
| 1 | 5 | True | — | What happened to microsoft/vscode CI? |
| 2 | 5 | True | — | Any pushes to redis/redis? |
| 3 | 1 | False | AWS us-east-1 region is down which caused it. | Issues on facebook/react? |
| 4 | 5 | True | — | PR merges in rust-lang/rust |
| 5 | 3 | False | Docker Hub was breached today. | Stars on golang/go |
| 6 | 5 | True | — | Terraform CI failures |
| 7 | 5 | True | — | deno memory leak issue? |
| 8 | 1 | False | Linus personally approved the fork in a private email. | Forks of linux? |
