import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv()

from agent import rewrite_query_text
from ingest import (
    COLL,
    dense_only_search,
    index_docs,
    reset_index,
    search,
)

ROOT = Path(__file__).parent
TS = ROOT / "testsets" / "retrieval.json"
SEED_FILE = ROOT / "testsets" / "retrieval_seed.json"
OUT = ROOT / "results_retrieval.md"
METRICS = ROOT / "metrics_retrieval.json"
K = 5
K3 = 3
EVAL_COLL = "eval_retrieval"


def load_seed():
    return json.loads(SEED_FILE.read_text())


def seed_index(rows):
    texts, metas, ids = [], [], []
    for row in rows:
        repo = row["repo"]
        et = row["event_type"]
        extra = row["extra"]
        t = f"event={et} | repo={repo} | actor=bot | at=2024-06-01T12:00:00Z | {extra}"
        texts.append(t)
        metas.append(
            {
                "repo": repo,
                "event_type": et,
                "text": t,
                "timestamp": "2024-06-01T12:00:00Z",
            }
        )
        ids.append(str(uuid.uuid4()))
    index_docs(texts, metas, ids)
    return len(texts)


def hit(docs, repo, et):
    for d in docs:
        if d.get("repo") == repo and (not et or d.get("event_type") == et):
            return True
    return False


def precision_at_k(docs, repo, et, k):
    top = docs[:k]
    if not top:
        return 0.0
    good = sum(1 for d in top if d.get("repo") == repo and d.get("event_type") == et)
    return good / len(top)


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    import ingest as ingest_mod

    ingest_mod.COLL = EVAL_COLL
    cases = json.loads(TS.read_text())
    reset_index(EVAL_COLL)
    n = seed_index(load_seed())
    print(f"seeded {n} docs")

    main_cases = [c for c in cases if not c.get("vague")]
    vague_cases = [c for c in cases if c.get("vague")]

    dense_precs, hybrid_precs = [], []
    recalls5, recalls3 = [], []
    lines = [
        "| # | query | hit@3 | hit@5 | P@5 dense | P@5 hybrid |",
        "|---|---|---|---|---|---|",
    ]

    for i, c in enumerate(main_cases, 1):
        dense_docs = dense_only_search(c["query"], K)
        hybrid_docs = search(c["query"], k=K)
        h5 = hit(hybrid_docs, c["expected_repo"], c["expected_type"])
        h3 = hit(hybrid_docs[:K3], c["expected_repo"], c["expected_type"])
        p_dense = precision_at_k(dense_docs, c["expected_repo"], c["expected_type"], K)
        p_hybrid = precision_at_k(hybrid_docs, c["expected_repo"], c["expected_type"], K)
        dense_precs.append(p_dense)
        hybrid_precs.append(p_hybrid)
        recalls5.append(1.0 if h5 else 0.0)
        recalls3.append(1.0 if h3 else 0.0)
        lines.append(
            f"| {i} | {c['query'][:40]} | {h3} | {h5} | {p_dense:.2f} | {p_hybrid:.2f} |"
        )

    stale_q = "workflow failures on shopify/hydrogen CI conclusion=failure"
    stale_docs = search(stale_q, k=K)
    stale_hit = any(d.get("repo") == "shopify/hydrogen" for d in stale_docs)
    stale_recall = 1.0 if stale_hit else 0.0

    fresh_text = (
        "event=WorkflowRunEvent | repo=shopify/hydrogen | actor=bot | "
        "at=2024-08-01T09:00:00Z | conclusion=failure | name=CI"
    )
    index_docs(
        [fresh_text],
        [
            {
                "repo": "shopify/hydrogen",
                "event_type": "WorkflowRunEvent",
                "text": fresh_text,
                "timestamp": "2024-08-01T09:00:00Z",
            }
        ],
        [str(uuid.uuid4())],
    )
    fresh_docs = search(stale_q, k=K3)
    fresh_hit = any(d.get("repo") == "shopify/hydrogen" for d in fresh_docs)
    fresh_recall3 = 1.0 if fresh_hit else 0.0

    rewrite_lines = [
        "| # | raw query | rewritten | hit@3 raw | hit@3 rewritten |",
        "|---|---|---|---|---|",
    ]
    raw_hits, rw_hits = [], []
    for i, c in enumerate(vague_cases, 1):
        raw_docs = search(c["query"], k=K3)
        rewritten = rewrite_query_text(c["query"])
        rw_docs = search(rewritten, k=K3)
        h_raw = hit(raw_docs, c["expected_repo"], c["expected_type"])
        h_rw = hit(rw_docs, c["expected_repo"], c["expected_type"])
        raw_hits.append(1.0 if h_raw else 0.0)
        rw_hits.append(1.0 if h_rw else 0.0)
        rewrite_lines.append(
            f"| {i} | {c['query'][:36]} | {rewritten[:36]} | {h_raw} | {h_rw} |"
        )

    r3 = mean(recalls3)
    r5 = mean(recalls5)
    p_dense = mean(dense_precs)
    p_hybrid = mean(hybrid_precs)
    r3_raw = mean(raw_hits)
    r3_rw = mean(rw_hits)

    metrics = {
        "recall_at_3": r3,
        "recall_at_5": r5,
        "precision_at_5": p_hybrid,
        "precision_at_5_dense": p_dense,
        "precision_at_5_hybrid": p_hybrid,
        "stale_recall": stale_recall,
        "fresh_recall_at_3": fresh_recall3,
        "rewrite_recall_at_3_raw": r3_raw,
        "rewrite_recall_at_3_rewritten": r3_rw,
        "cases": len(main_cases),
        "vague_cases": len(vague_cases),
    }
    METRICS.write_text(json.dumps(metrics, indent=2))

    summary = [
        "# Retrieval eval",
        "",
        f"- cases: {len(main_cases)} (+ {len(vague_cases)} vague rewrite cases)",
        f"- Recall@{K3}: **{r3:.3f}**",
        f"- Recall@{K}: **{r5:.3f}**",
        f"- Precision@{K} dense-only (before): **{p_dense:.3f}**",
        f"- Precision@{K} hybrid+filter+rerank (after): **{p_hybrid:.3f}**",
        f"- delta P@{K}: **{p_hybrid - p_dense:+.3f}**",
        f"- stale (shopify/hydrogen before ingest): hit={stale_hit} recall={stale_recall:.3f}",
        f"- fresh (after ingest) Recall@3: hit={fresh_hit} recall={fresh_recall3:.3f}",
        "",
        "## Hybrid vs dense Precision@5",
        "",
        *lines,
        "",
        "## Query rewrite (vague cases)",
        "",
        f"- Recall@3 raw: **{r3_raw:.3f}**",
        f"- Recall@3 rewritten: **{r3_rw:.3f}**",
        f"- delta: **{r3_rw - r3_raw:+.3f}**",
        "",
        *rewrite_lines,
        "",
    ]
    OUT.write_text("\n".join(summary))
    print("\n".join(summary))

    ingest_mod.COLL = COLL


if __name__ == "__main__":
    main()
