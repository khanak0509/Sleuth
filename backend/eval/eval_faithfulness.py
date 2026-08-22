import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv()

ROOT = Path(__file__).parent
TS = ROOT / "testsets" / "faithfulness.json"
OUT = ROOT / "results_faithfulness.md"
METRICS = ROOT / "metrics_faithfulness.json"


class Faith(BaseModel):
    faithful_score: int = Field(ge=1, le=5)
    unsupported_claims: list[str] = Field(default_factory=list)


def score(llm, query, docs, answer):
    blob = "\n".join(docs)
    prompt = PromptTemplate.from_template(
        """Score whether the answer's claims are supported by the docs.
faithful_score: integer 1-5
- 5: every claim grounded in docs
- 3: mostly grounded, minor stretch
- 1: major unsupported / invented claims
List unsupported_claims explicitly (empty if none).

Query: {query}

Docs:
{docs}

Answer:
{answer}
"""
    )
    chain = prompt | llm.with_structured_output(Faith)
    return chain.invoke({"query": query, "docs": blob, "answer": answer})


def main():
    cases = json.loads(TS.read_text())
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    all_scores = []
    grounded_scores = []
    low = []
    rows = ["| # | score | expect_faithful | unsupported | query |", "|---|---|---|---|---|"]

    for i, c in enumerate(cases, 1):
        f = score(llm, c["query"], c["docs"], c["answer"])
        all_scores.append(f.faithful_score)
        if c.get("expect_faithful", True):
            grounded_scores.append(f.faithful_score)
        if f.faithful_score <= 2:
            low.append({"query": c["query"], "score": f.faithful_score, "claims": f.unsupported_claims})
        claims = "; ".join(f.unsupported_claims)[:60] or "—"
        rows.append(
            f"| {i} | {f.faithful_score} | {c.get('expect_faithful', True)} | {claims} | {c['query'][:40]} |"
        )

    mean_all = sum(all_scores) / len(all_scores) if all_scores else 0.0
    mean_grounded = (
        sum(grounded_scores) / len(grounded_scores) if grounded_scores else 0.0
    )

    metrics = {
        "mean_faithful_score": mean_grounded,
        "mean_all_including_planted": mean_all,
        "low_score_flags": low,
        "grounded_cases": len(grounded_scores),
        "cases": len(cases),
    }
    METRICS.write_text(json.dumps(metrics, indent=2))

    md = [
        "# Faithfulness eval",
        "",
        f"- cases: {len(cases)}",
        f"- mean faithful_score on expect_faithful=true: **{mean_grounded:.2f}**",
        f"- mean including planted hallucinations: **{mean_all:.2f}**",
        f"- answers scoring <=2 (manual review): {len(low)}",
        "",
        *rows,
        "",
    ]
    OUT.write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
