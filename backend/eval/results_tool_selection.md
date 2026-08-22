# Tool selection eval

- cases: 23
- accuracy (exact preferred tool): **1.000**
- soft accuracy (preferred or also_plausible): **1.000**

| # | gold | pred | ok | soft | incident |
|---|---|---|---|---|---|
| 1 | restart_pod | restart_pod | True | True | Pod crashlooping after OOMKilled in namesp |
| 2 | block_ip | block_ip | True | True | Suspicious scraper hitting auth endpoints  |
| 3 | rollback_deploy | rollback_deploy | True | True | Error rate spiked right after deploying pa |
| 4 | scale_replica | scale_replica | True | True | Checkout service CPU pegged under Black Fr |
| 5 | page_oncall | page_oncall | True | True | Sev1: cascading failures across regions, r |
| 6 | none | none | True | True | Mild increase in WatchEvents on a public r |
| 7 | restart_pod | restart_pod | True | True | Unhealthy replica stuck, kubectl describe  |
| 8 | block_ip | block_ip | True | True | Botnet scanning from 198.51.100.10 causing |
| 9 | rollback_deploy | rollback_deploy | True | True | Bad feature flag shipped with web-frontend |
| 10 | scale_replica | scale_replica | True | True | Queue depth rising, only 1 consumer replic |
| 11 | page_oncall | page_oncall | True | True | Database failover mid-incident and paging  |
| 12 | none | none | True | True | Summarize recent PushEvents for redis/redi |
| 13 | restart_pod | restart_pod | True | True | Container repeatedly exits with code 137 i |
| 14 | block_ip | block_ip | True | True | Credential stuffing from 192.0.2.88 agains |
| 15 | rollback_deploy | rollback_deploy | True | True | Canary of billing-service looks bad, rever |
| 16 | restart_pod | restart_pod | True | True | One api pod in CrashLoopBackOff after a ba |
| 17 | block_ip | block_ip | True | True | Suspicious IP 203.0.113.9 is hammering log |
| 18 | rollback_deploy | rollback_deploy | True | True | After deploy checkout-v9 latency exploded  |
| 19 | scale_replica | scale_replica | True | True | Known-good build, sudden 10x QPS, pods hea |
| 20 | page_oncall | page_oncall | True | True | Symptoms span DNS, DB, and edge; no single |
| 21 | none | none | True | True | CI is red on a public repo in the logs but |
| 22 | rollback_deploy | rollback_deploy | True | True | Bad canary is live and also one replica is |
| 23 | block_ip | block_ip | True | True | Auth abuse from a single /24 plus mild CPU |
