import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv()

ROOT = Path(__file__).parent
TS = ROOT / "testsets" / "retrieval.json"
SEED_FILE = ROOT / "testsets" / "retrieval_seed.json"
OUT = ROOT / "results_retrieval.md"
METRICS = ROOT / "metrics_retrieval.json"
K = 5
K3 = 3
COLL = "eval_retrieval"


def load_seed():
    return json.loads(SEED_FILE.read_text())


def make_store():
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    return QdrantVectorStore(
        embedding=emb,
        collection_name=COLL,
        location=":memory:",
    )


def seed_index(store, rows):
    texts, metas, ids = [], [], []
    for row in rows:
        repo = row["repo"]
        et = row["event_type"]
        extra = row["extra"]
        t = f"event={et} | repo={repo} | actor=bot | at=2024-06-01T12:00:00Z | {extra}"
        texts.append(t)
        metas.append({"repo": repo, "event_type": et, "text": t, "timestamp": "2024-06-01T12:00:00Z"})
        ids.append(str(uuid.uuid4()))
    store.add_texts(texts, metadatas=metas, ids=ids)
    return len(texts)


def search_store(store, q, k=K):
    hits = store.similarity_search_with_score(q, k=k)
    return [doc.metadata or {} for doc, _ in hits]


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


def main():
    cases = json.loads(TS.read_text())
    store = make_store()

    n = seed_index(store, load_seed())
    print(f"seeded {n} docs")

    recalls5, recalls3, precs = [], [], []
    lines = ["| # | query | hit@3 | hit@5 | P@5 |", "|---|---|---|---|---|"]

    for i, c in enumerate(cases, 1):
        docs = search_store(store, c["query"], K)
        h5 = hit(docs, c["expected_repo"], c["expected_type"])
        h3 = hit(docs[:K3], c["expected_repo"], c["expected_type"])
        p = precision_at_k(docs, c["expected_repo"], c["expected_type"], K)
        recalls5.append(1.0 if h5 else 0.0)
        recalls3.append(1.0 if h3 else 0.0)
        precs.append(p)
        lines.append(
            f"| {i} | {c['query'][:48]} | {h3} | {h5} | {p:.2f} |"
        )

    stale_q = "workflow failures on shopify/hydrogen CI conclusion=failure"
    stale_docs = search_store(store, stale_q, K)
    stale_hit = any(d.get("repo") == "shopify/hydrogen" for d in stale_docs)
    stale_recall = 1.0 if stale_hit else 0.0

    fresh_text = (
        "event=WorkflowRunEvent | repo=shopify/hydrogen | actor=bot | "
        "at=2024-08-01T09:00:00Z | conclusion=failure | name=CI"
    )
    store.add_texts(
        [fresh_text],
        metadatas=[
            {
                "repo": "shopify/hydrogen",
                "event_type": "WorkflowRunEvent",
                "text": fresh_text,
                "timestamp": "2024-08-01T09:00:00Z",
            }
        ],
        ids=[str(uuid.uuid4())],
    )
    fresh_docs = search_store(store, stale_q, K3)
    fresh_hit = any(d.get("repo") == "shopify/hydrogen" for d in fresh_docs)
    fresh_recall3 = 1.0 if fresh_hit else 0.0

    r3 = sum(recalls3) / len(recalls3)
    r5 = sum(recalls5) / len(recalls5)
    p_mean = sum(precs) / len(precs)

    metrics = {
        "recall_at_3": r3,
        "recall_at_5": r5,
        "precision_at_5": p_mean,
        "stale_recall": stale_recall,
        "fresh_recall_at_3": fresh_recall3,
        "cases": len(cases),
    }
    METRICS.write_text(json.dumps(metrics, indent=2))

    summary = [
        "# Retrieval eval",
        "",
        f"- cases: {len(cases)}",
        f"- Recall@{K3}: **{r3:.3f}**",
        f"- Recall@{K}: **{r5:.3f}**",
        f"- Precision@{K} (mean): **{p_mean:.3f}**",
        f"- stale (shopify/hydrogen before ingest): hit={stale_hit} recall={stale_recall:.3f}",
        f"- fresh (after ingest) Recall@3: hit={fresh_hit} recall={fresh_recall3:.3f}",
        "",
        *lines,
        "",
    ]
    OUT.write_text("\n".join(summary))
    print("\n".join(summary))


if __name__ == "__main__":
    main()
