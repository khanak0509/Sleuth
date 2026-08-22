import hashlib
import os
import threading
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv()

COLL = "github_events"
POLL_SEC = 5
BATCH = 30

GH_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "sleuth-rag"}
github_token = os.getenv("GITHUB_TOKEN")
if github_token:
    GH_HEADERS["Authorization"] = f"Bearer {github_token}"

embeddings = None
vector_store = None


def get_embeddings():
    global embeddings
    if embeddings is None:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return embeddings


def get_vector_store():
    global vector_store
    if vector_store is None:
        vector_store = QdrantVectorStore(
            embedding=get_embeddings(),
            collection_name=COLL,
            location=":memory:",
        )
    return vector_store

stats = {
    "event_count": 0,
    "last_ts": None,
    "seen": set(),
    "running": False,
}


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

    get_vector_store().add_texts(
        texts=[t for _, t, _ in fresh],
        metadatas=[m for _, _, m in fresh],
        ids=[eid for eid, _, _ in fresh],
    )

    stats["event_count"] += len(fresh)
    last = max((m["timestamp"] for _, _, m in fresh), default=None)
    if last:
        stats["last_ts"] = last
    return len(fresh)


def search(q, k=5):
    hits = get_vector_store().similarity_search_with_score(q, k=k)
    docs = []
    for doc, score in hits:
        meta = doc.metadata or {}
        docs.append(
            {
                "text": meta.get("text", doc.page_content),
                "repo": meta.get("repo", ""),
                "event_type": meta.get("event_type", ""),
                "timestamp": meta.get("timestamp", ""),
                "score": float(score) if score is not None else 0.0,
            }
        )
    return docs


def ingest_loop(stop_evt: threading.Event | None = None):
    stats["running"] = True
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
