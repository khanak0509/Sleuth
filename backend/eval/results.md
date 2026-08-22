# Eval gate report

**Overall: FAIL (1 metric(s) below threshold)**

| metric | result | threshold | status |
|---|---|---|---|
| Retrieval Recall@3 (fresh seed) | 1.000 | >= 0.8 | **PASS** |
| Retrieval Recall on stale (not ingested) | 0.000 | ~0 (expected miss, <= 0.15) | **PASS** |
| Grading false-positive rate | 0.125 | <= 0.1 | **FAIL** |
| Fallback trigger accuracy | 1.000 | >= 0.85 | **PASS** |
| Tool selection accuracy | 1.000 | >= 0.8 | **PASS** |
| Input guardrail catch rate | 1.000 | >= 0.9 | **PASS** |
| Output guardrail catch rate | 1.000 | >= 0.85 | **PASS** |
| Output guardrail false-flag rate | 0.000 | <= 0.15 | **PASS** |
| Faithfulness mean (1-5, grounded cases) | 5.000 | >= 4.0 | **PASS** |

## Notes

- manual review: 2 answer(s) scored <=2
  - score=1: Issues on facebook/react?
  - score=1: Forks of linux?
- stale recall near 0 is expected (proves the moving-index check is real, not a bug)
