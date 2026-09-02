import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, VectorParams
from rank_bm25 import BM25Okapi

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv()

COLL = "github_events"
POLL_SEC = 5
BATCH = 30
SEED_FILE = Path(__file__).parent / "eval" / "testsets" / "retrieval_seed.json"
CANDIDATE_K = 15
RRF_K = 60
EMBED_DIM = 1536

GH_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "sleuth-rag"}
github_token = os.getenv("GITHUB_TOKEN")
if github_token:
    GH_HEADERS["Authorization"] = f"Bearer {github_token}"

REPO_ALIASES = {
    "vscode": "microsoft/vscode",
    "kubernetes": "kubernetes/kubernetes",
    "k8s": "kubernetes/kubernetes",
    "react": "facebook/react",
    "rust": "rust-lang/rust",
    "tensorflow": "tensorflow/tensorflow",
    "golang": "golang/go",
    "linux": "torvalds/linux",
    "node": "nodejs/node",
    "nodejs": "nodejs/node",
    "spark": "apache/spark",
    "angular": "angular/angular",
    "pytorch": "pytorch/pytorch",
    "homebrew": "homebrew/brew",
    "brew": "homebrew/brew",
    "elasticsearch": "elastic/elasticsearch",
    "next.js": "vercel/next.js",
    "nextjs": "vercel/next.js",
    "terraform": "hashicorp/terraform",
    "deno": "denoland/deno",
    "django": "django/django",
    "redis": "redis/redis",
    "grafana": "grafana/grafana",
}

EVENT_ALIASES = {
    "workflow": "WorkflowRunEvent",
    "workflows": "WorkflowRunEvent",
    "workflowrun": "WorkflowRunEvent",
    "ci": "WorkflowRunEvent",
    "push": "PushEvent",
    "pushes": "PushEvent",
    "issue": "IssuesEvent",
    "issues": "IssuesEvent",
    "pr": "PullRequestEvent",
    "prs": "PullRequestEvent",
    "pull": "PullRequestEvent",
    "pullrequest": "PullRequestEvent",
    "watch": "WatchEvent",
    "star": "WatchEvent",
    "starred": "WatchEvent",
    "fork": "ForkEvent",
    "release": "ReleaseEvent",
    "create": "CreateEvent",
    "delete": "DeleteEvent",
}

embeddings = None
qdrant_client = None
vector_store = None
cross_encoder = None

bm25_index = None
bm25_tokens = []
bm25_docs = []


def get_embeddings():
    global embeddings
    if embeddings is None:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return embeddings


def get_qdrant_client():
    global qdrant_client
    if qdrant_client is None:
        qdrant_client = QdrantClient(location=":memory:")
    return qdrant_client


def ensure_collection(client, name):
    try:
        client.get_collection(name)
    except Exception:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )


def get_vector_store():
    global vector_store
    if vector_store is None:
        client = get_qdrant_client()
        ensure_collection(client, COLL)
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=COLL,
            embedding=get_embeddings(),
        )
    return vector_store


def get_cross_encoder():
    global cross_encoder
    if cross_encoder is None:
        from sentence_transformers import CrossEncoder

        cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return cross_encoder


stats = {
    "event_count": 0,
    "last_ts": None,
    "seen": set(),
    "running": False,
}


def tokenize(text):
    return re.findall(r"[a-z0-9_./+-]+", (text or "").lower())


def rebuild_bm25():
    global bm25_index
    bm25_index = BM25Okapi(bm25_tokens) if bm25_tokens else None


def add_to_bm25(texts, metas):
    for t, m in zip(texts, metas):
        row = dict(m)
        row["text"] = row.get("text") or t
        bm25_docs.append(row)
        bm25_tokens.append(tokenize(t))
    rebuild_bm25()


def flatten_event(ev):
    et = ev.get("type", "Unknown")
    repo = (ev.get("repo") or {}).get("name", "unknown/unknown")
    actor = (ev.get("actor") or {}).get("login", "unknown")
    created = ev.get("created_at", "")
    payload = ev.get("payload") or {}

    bits = [f"event={et}", f"repo={repo}", f"actor={actor}", f"at={created}"]

    if et == "PushEvent":
        commits = payload.get("commits") or []
        msgs = [c.get("message", "")[:80] for c in commits[:3]]
        bits.append(f"commits={len(commits)}")
        if msgs:
            bits.append("messages=" + " | ".join(msgs))
    elif et == "IssuesEvent":
        issue = payload.get("issue") or {}
        bits.append(f"action={payload.get('action')}")
        bits.append(f"title={issue.get('title', '')}")
        bits.append(f"state={issue.get('state', '')}")
    elif et == "PullRequestEvent":
        pr = payload.get("pull_request") or {}
        bits.append(f"action={payload.get('action')}")
        bits.append(f"title={pr.get('title', '')}")
        bits.append(f"merged={pr.get('merged')}")
    elif et == "WorkflowRunEvent":
        wr = payload.get("workflow_run") or {}
        bits.append(f"action={payload.get('action')}")
        bits.append(f"name={wr.get('name', '')}")
        bits.append(f"conclusion={wr.get('conclusion')}")
        bits.append(f"status={wr.get('status')}")
    elif et == "CreateEvent":
        bits.append(f"ref_type={payload.get('ref_type')}")
        bits.append(f"ref={payload.get('ref')}")
    elif et == "DeleteEvent":
        bits.append(f"ref_type={payload.get('ref_type')}")
        bits.append(f"ref={payload.get('ref')}")
    elif et == "WatchEvent":
        bits.append(f"action={payload.get('action')}")
    elif et == "ForkEvent":
        fr = payload.get("forkee") or {}
        bits.append(f"fork={fr.get('full_name', '')}")
    elif et == "ReleaseEvent":
        rel = payload.get("release") or {}
        bits.append(f"action={payload.get('action')}")
        bits.append(f"tag={rel.get('tag_name', '')}")
    else:
        bits.append(f"keys={list(payload.keys())[:8]}")

    text = " | ".join(str(b) for b in bits if b)
    meta = {
        "repo": repo,
        "event_type": et,
        "actor": actor,
        "timestamp": created,
        "text": text,
    }
    return text, meta


def event_id(ev):
    raw = f"{ev.get('id')}:{ev.get('type')}:{(ev.get('repo') or {}).get('name')}"
    h = hashlib.md5(raw.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def fetch_events():
    url = "https://api.github.com/events"
    with httpx.Client(timeout=20) as http:
        r = http.get(url, headers=GH_HEADERS, params={"per_page": BATCH})
        remaining = r.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) == 0:
            reset = int(r.headers.get("X-RateLimit-Reset", "0"))
            wait = max(reset - int(time.time()), POLL_SEC)
            time.sleep(min(wait, 60))
            return []
        if r.status_code == 403:
            time.sleep(30)
            return []
        r.raise_for_status()
        return r.json()


def extract_filters(q):
    q_low = (q or "").lower()
    repos = []
    et = None

    for m in re.finditer(r"\b([a-z0-9_.-]+/[a-z0-9_.-]+)\b", q_low):
        repos.append(m.group(1))

    if not repos:
        for alias, full in REPO_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", q_low):
                if full not in repos:
                    repos.append(full)

    for alias, full in EVENT_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", q_low):
            et = full
            break

    repo = repos[0] if len(repos) == 1 else None
    return {"repo": repo, "event_type": et}


def matches_filter(doc, filt):
    if not filt:
        return True
    if filt.get("repo") and doc.get("repo", "").lower() != filt["repo"].lower():
        return False
    if filt.get("event_type") and doc.get("event_type") != filt["event_type"]:
        return False
    return True


def doc_key(doc):
    return f"{doc.get('repo','')}|{doc.get('event_type','')}|{doc.get('text','')}"


def rrf_fuse(rank_lists, k=RRF_K):
    scores = {}
    docs_by_key = {}
    for ranks in rank_lists:
        for i, doc in enumerate(ranks):
            key = doc_key(doc)
            docs_by_key[key] = doc
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + i + 1)
    ordered = sorted(scores.items(), key=lambda x: -x[1])
    out = []
    for key, score in ordered:
        d = dict(docs_by_key[key])
        d["score"] = score
        out.append(d)
    return out


def bm25_search(q, k=CANDIDATE_K, filt=None):
    if not bm25_index or not bm25_docs:
        return []
    scores = bm25_index.get_scores(tokenize(q))
    ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
    out = []
    for i in ranked:
        doc = bm25_docs[i]
        if not matches_filter(doc, filt):
            continue
        row = dict(doc)
        row["score"] = float(scores[i])
        out.append(row)
        if len(out) >= k:
            break
    return out


def vector_search(q, k=CANDIDATE_K, filt=None):
    store = get_vector_store()
    qdrant_filter = None
    must = []
    if filt and filt.get("repo"):
        must.append(
            FieldCondition(key="metadata.repo", match=MatchValue(value=filt["repo"]))
        )
    if filt and filt.get("event_type"):
        must.append(
            FieldCondition(
                key="metadata.event_type", match=MatchValue(value=filt["event_type"])
            )
        )
    if must:
        qdrant_filter = Filter(must=must)

    try:
        hits = store.similarity_search_with_score(q, k=k, filter=qdrant_filter)
    except Exception:
        hits = store.similarity_search_with_score(q, k=k)

    docs = []
    for doc, score in hits:
        meta = doc.metadata or {}
        row = {
            "text": meta.get("text", doc.page_content),
            "repo": meta.get("repo", ""),
            "event_type": meta.get("event_type", ""),
            "timestamp": meta.get("timestamp", ""),
            "score": float(score) if score is not None else 0.0,
        }
        if matches_filter(row, filt):
            docs.append(row)
    return docs


def rerank(q, docs, top_k=5):
    if not docs:
        return []
    if len(docs) == 1:
        return docs[:top_k]
    try:
        model = get_cross_encoder()
        pairs = [(q, d.get("text", "")) for d in docs]
        scores = model.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: -float(x[1]))
        out = []
        for doc, score in ranked[:top_k]:
            row = dict(doc)
            row["score"] = float(score)
            out.append(row)
        return out
    except Exception as e:
        print(f"rerank fallback: {e}")
        return docs[:top_k]


def search(q, k=5, candidate_k=CANDIDATE_K, use_rerank=True, use_filter=True):
    filt = extract_filters(q) if use_filter else {"repo": None, "event_type": None}
    if not filt.get("repo") and not filt.get("event_type"):
        filt = None

    dense = vector_search(q, k=candidate_k, filt=filt)
    sparse = bm25_search(q, k=candidate_k, filt=filt)

    if not dense and not sparse:
        return []
    if not dense:
        fused = sparse
    elif not sparse:
        fused = dense
    else:
        fused = rrf_fuse([dense, sparse])

    fused = fused[:candidate_k]
    if use_rerank:
        return rerank(q, fused, top_k=k)
    return fused[:k]


def upsert_events(events):
    fresh = []
    for ev in events:
        eid = event_id(ev)
        if eid in stats["seen"]:
            continue
        stats["seen"].add(eid)
        text, meta = flatten_event(ev)
        fresh.append((eid, text, meta))

    if not fresh:
        return 0

    texts = [t for _, t, _ in fresh]
    metas = [m for _, _, m in fresh]
    ids = [eid for eid, _, _ in fresh]

    get_vector_store().add_texts(texts=texts, metadatas=metas, ids=ids)
    add_to_bm25(texts, metas)

    stats["event_count"] += len(fresh)
    last = max((m["timestamp"] for _, _, m in fresh), default=None)
    if last:
        stats["last_ts"] = last
    return len(fresh)


def reset_index(collection_name=COLL):
    global vector_store, bm25_docs, bm25_tokens, bm25_index, qdrant_client
    bm25_docs = []
    bm25_tokens = []
    bm25_index = None
    vector_store = None
    client = get_qdrant_client()
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    ensure_collection(client, collection_name)
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=get_embeddings(),
    )
    return vector_store


def index_docs(texts, metas, ids):
    get_vector_store().add_texts(texts=texts, metadatas=metas, ids=ids)
    add_to_bm25(texts, metas)


def dense_only_search(q, k=5):
    return vector_search(q, k=k, filt=None)[:k]


def seed_bootstrap():
    if not SEED_FILE.exists():
        return 0
    rows = json.loads(SEED_FILE.read_text())
    texts, metas, ids = [], [], []
    ts = "2024-06-01T12:00:00Z"
    for row in rows:
        repo = row["repo"]
        et = row["event_type"]
        extra = row["extra"]
        t = f"event={et} | repo={repo} | actor=github-actions[bot] | at={ts} | {extra}"
        eid = event_id({"id": t, "type": et, "repo": {"name": repo}})
        if eid in stats["seen"]:
            continue
        stats["seen"].add(eid)
        texts.append(t)
        metas.append(
            {
                "repo": repo,
                "event_type": et,
                "actor": "github-actions[bot]",
                "timestamp": ts,
                "text": t,
            }
        )
        ids.append(eid)

    if not texts:
        return 0

    get_vector_store().add_texts(texts, metadatas=metas, ids=ids)
    add_to_bm25(texts, metas)
    stats["event_count"] += len(texts)
    stats["last_ts"] = ts
    print(f"seeded {len(texts)} bootstrap events")
    return len(texts)


def ingest_loop(stop_evt: threading.Event | None = None):
    stats["running"] = True
    try:
        seed_bootstrap()
    except Exception as e:
        print(f"seed error: {e}")
    while True:
        if stop_evt and stop_evt.is_set():
            break
        try:
            evs = fetch_events()
            n = upsert_events(evs)
            if n:
                print(f"ingested {n} events, total={stats['event_count']}")
        except Exception as e:
            print(f"ingest error: {e}")
        time.sleep(POLL_SEC)
    stats["running"] = False


def start_ingest_thread():
    t = threading.Thread(target=ingest_loop, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print(f"polling github events every {POLL_SEC}s -> qdrant {COLL}")
    ingest_loop()
