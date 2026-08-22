# Sleuth

Live incident-response RAG demo. It polls GitHub’s public Events API, embeds each event into Qdrant, and answers investigation queries through a LangGraph pipeline (retrieve → grade → answer or web fallback → mock tool pick) with input/output guardrails.

Built as a portfolio piece: fewer features, more eval rigor.

## Where does the data come from?


| Source                                             | What it is                                                                                                   | Auth                                                      |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| [GitHub Events API](https://api.github.com/events) | Real public timeline (pushes, issues, PRs, workflow runs, …) polled every few seconds by `backend/ingest.py` | None required; optional `GITHUB_TOKEN` raises rate limits |
| OpenAI                                             | Embeddings (`text-embedding-3-small`) + `gpt-4o-mini` for grading, answers, tools, guardrails                | `OPENAI_API_KEY` in `.env`                                |
| DuckDuckGo (`ddgs`)                                | Used only when the grader says local logs are weak (fallback path)                                           | No key                                                    |


There is no canned log file. The corkboard sticky note’s event count rises because new public GitHub events are actually landing while the API runs.

## What is [http://127.0.0.1:5173](http://127.0.0.1:5173)?

That is the **Vite React frontend** (local only).


| URL                                            | Process                           |
| ---------------------------------------------- | --------------------------------- |
| [http://127.0.0.1:5173](http://127.0.0.1:5173) | UI (`npm run dev` in `frontend/`) |
| [http://127.0.0.1:8000](http://127.0.0.1:8000) | FastAPI (`uvicorn` in `backend/`) |


The UI proxies `/incident` and `/stream` to port 8000 (see `frontend/vite.config.js`). Open 5173 in a browser; you do not open 8000 for the corkboard.

## Quick start

```bash
cp .env.example .env          # set OPENAI_API_KEY

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000

# other terminal
cd frontend
npm install
npm run dev
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173).

## Architecture

```
GitHub Events API ──poll──▶ ingest.py ──embed──▶ Qdrant (:memory:)
                                                    │
POST /incident ──▶ input guardrail ──▶ LangGraph:
                     │                    retrieve → grade
                     │                         │
                     │              relevant? ─┼─ yes → answer
                     │                         └─ no  → fallback (ddgs)
                     │                                    │
                     │                              pick_tool (mock)
                     └──────────────────────────▶ output guardrail → JSON
```


| File                    | Role                                                            |
| ----------------------- | --------------------------------------------------------------- |
| `backend/ingest.py`     | Poll, flatten, embed, upsert; exposes search + live `stats`     |
| `backend/agent.py`      | LangGraph state machine                                         |
| `backend/tools.py`      | Mock ops tools + structured selection (log only, no real infra) |
| `backend/guardrails.py` | Input / output checks                                           |
| `backend/main.py`       | `POST /incident`, `GET /stream/status`                          |
| `frontend/`             | Corkboard UI                                                    |


LLM calls use `chain = prompt | llm | parser` (or `.with_structured_output`), model `gpt-4o-mini` only.

### Known limitation: Qdrant `:memory:`

The vector store is **in-process** `:memory:`. Restarting the API **wipes the index**; ingest starts from zero again. That is a deliberate demo-scope choice (no Docker, no disk lock fights), not an accidental omission.

A production version would use a durable Qdrant (local path / Docker / hosted) with a persistent collection and the same upsert/search API.

## API

`POST /incident`

```json
{ "query": "Any WorkflowRun failures showing up in recent logs?" }
```

```json
{
  "answer": "...",
  "path_taken": "direct | fallback | rejected",
  "tool_used": "restart_pod | none | ...",
  "grade_reason": "...",
  "retrieved_docs": [],
  "rejected": false
}
```

`GET /stream/status` → `{ event_count, last_ingested_timestamp, running }`

## Evaluation (how the numbers got here)

Stages are scored separately — retrieval, grading, fallback, tools, guardrails, faithfulness — because RAG fails differently at each hop.

```bash
cd backend && source .venv/bin/activate
python eval/run_all.py    # writes eval/results.md + metrics_*.json
```



### Eval methodology (kept on purpose)

1. **First pass was too easy.** Early retrieval/grading queries nearly paraphrased their gold docs with no real distractors, so scores looked like a clean 100%. Sets were hardened with lookalike incidents (same failure mode across different repos: memory leaks, state-management bugs, CI failures) without “not X / rather than X” negation cues that hand the model the answer.
2. **Output guardrail silently over-flagged.** Catch rate alone looked fine while safe answers (“suggest rolling back…”, factual CI summaries) were rejected. An **output false-flag rate** was added and gated (`<= 0.15`), and the prompt was tightened to allow recommendations / log facts while still catching past-tense “I already restarted…” claims.
3. **Numbers are reported as measured.** If lookalike cases drop Recall or raise grading FPR, that drop stays in the table — cases are not retuned until they pass.



### Latest gate (`eval/results.md`)


| metric                           | result    | threshold    | status          |
| -------------------------------- | --------- | ------------ | --------------- |
| Retrieval Recall@3               | **1.000** | >= 0.80      | PASS            |
| Retrieval stale recall           | **0.000** | ~0 (<= 0.15) | PASS            |
| Retrieval Precision@5 (mean)     | **0.362** | —            | (informational) |
| Grading false-positive rate      | **0.125** | <= 0.10      | **FAIL**        |
| Fallback trigger accuracy        | **1.000** | >= 0.85      | PASS            |
| Tool selection accuracy          | **1.000** | >= 0.80      | PASS            |
| Input guardrail catch rate       | **1.000** | >= 0.90      | PASS            |
| Output guardrail catch rate      | **1.000** | >= 0.85      | PASS            |
| Output guardrail false-flag rate | **0.000** | <= 0.15      | PASS            |
| Faithfulness mean (grounded)     | **5.00**  | >= 4.0       | PASS            |


**Overall: FAIL (1 metric)** — grading FPR **0.125** on lookalike negatives (3 FP / 24 safe-negative cases). The grader wrongly called docs “relevant” for cross-repo memory-leak lookalikes (Deno↔Node↔Next.js). Threshold stays at `<= 0.10`; cases were **not** softened to force a green gate.

Grading accuracy on the full set: **0.912** (34 cases). Retrieval lookalikes without negation cues still hit Recall@3 = 1.0; Precision@5 rose to **0.362** as more same-topic distractors land in top-k.

## Testing

See `[TESTING.md](TESTING.md)`.

```bash
cd backend && source .venv/bin/activate
.venv/bin/python -m pytest tests/ -v                    # unit; integration skipped
RUN_INTEGRATION=1 .venv/bin/python -m pytest tests/integration/ -v
python eval/run_all.py
```

## Thanks :) 

