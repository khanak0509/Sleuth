# Fallback trigger eval

- cases where fallback SHOULD fire: 5
- trigger rate when it should: **1.000**
- hold rate when it should NOT: **1.000**

| # | should_fallback | triggered | ok | query |
|---|---|---|---|---|
| 1 | True | True | True | Explain the latest AWS us-east-1 outage im |
| 2 | True | True | True | Why did my private Jenkins job fail last n |
| 3 | True | True | True | Historical root cause of the 2021 Fastly C |
| 4 | False | False | True | What does conclusion=failure mean for micr |
| 5 | False | False | True | Summarize push activity on redis/redis fro |
| 6 | False | False | True | Are there issue opens against denoland/den |
| 7 | True | True | True | How do I rotate AWS IAM keys after a leak? |
| 8 | False | False | True | PR merges listed for rust-lang/rust |
| 9 | True | True | True | Explain Kubernetes etcd quorum loss recove |
| 10 | False | False | True | Workflow failure burst on hashicorp/terraf |
