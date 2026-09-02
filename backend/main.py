import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import run_agent
from guardrails import REJECT_MSG, check_input, check_output, sanitize_answer
from ingest import start_ingest_thread, stats

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY missing — LLM routes will fail")
    start_ingest_thread()
    yield


app = FastAPI(title="Sleuth", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IncidentReq(BaseModel):
    query: str


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/stream/status")
def stream_status():
    return {
        "event_count": stats["event_count"],
        "last_ingested_timestamp": stats["last_ts"],
        "running": stats["running"],
        "unique_seen": len(stats["seen"]),
    }


@app.post("/incident")
def incident(req: IncidentReq):
    q = (req.query or "").strip()
    if not q:
        return {
            "answer": "Empty query.",
            "path_taken": "rejected",
            "tool_used": "none",
            "grade_reason": "",
            "retrieved_docs": [],
            "rejected": True,
        }

    gate = check_input(q)
    if not gate.safe:
        return {
            "answer": REJECT_MSG + f" ({gate.reason})",
            "path_taken": "rejected",
            "tool_used": "none",
            "grade_reason": gate.reason,
            "retrieved_docs": [],
            "rejected": True,
        }

    res = run_agent(q)
    out_gate = check_output(res["answer"])
    answer = res["answer"]
    if not out_gate.safe:
        answer = sanitize_answer(answer, out_gate.issues)

    return {
        "answer": answer,
        "path_taken": res["path_taken"],
        "tool_used": res["tool_used"],
        "grade_reason": res["grade_reason"],
        "retrieved_docs": res["retrieved_docs"],
        "grade_relevant": res["grade_relevant"],
        "rewritten_query": res.get("rewritten_query", ""),
        "rejected": False,
        "output_sanitized": not out_gate.safe,
    }
