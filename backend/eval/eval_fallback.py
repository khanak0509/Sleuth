import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv()

ROOT = Path(__file__).parent
TS = ROOT / "testsets" / "fallback.json"
OUT = ROOT / "results_fallback.md"

class Grade(BaseModel):
    relevant: bool
    reason: str

def grade(llm, query, docs):
    blob = "\n".join(docs) if docs else "(no docs)"
    prompt = PromptTemplate.from_template(
        """Judge whether these retrieved GitHub event logs help answer the incident query.
relevant=true only if the docs contain concrete signal about the repos/events asked.
If docs are empty, off-topic, or too weak, relevant=false.

Query: {query}

Docs:
{docs}

Return relevant and reason."""
    )
    chain = prompt | llm.with_structured_output(Grade)
    return chain.invoke({"query": query, "docs": blob})

def main():
    cases = json.loads(TS.read_text())
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    results = []
    for c in cases:
        g = grade(llm, c["query"], c["docs"])
        triggered = not g.relevant
        results.append((c, triggered))

    should = [c for c, _ in results if c["should_fallback"]]
    should_not = [c for c, _ in results if not c["should_fallback"]]
    trig_ok = sum(1 for c, t in results if c["should_fallback"] and t)
    hold_ok = sum(1 for c, t in results if (not c["should_fallback"]) and (not t))
    rate = trig_ok / len(should) if should else 0.0
    hold = hold_ok / len(should_not) if should_not else 0.0

    rows = ["| # | should_fallback | triggered | ok | query |", "|---|---|---|---|---|"]
    for i, (c, t) in enumerate(results, 1):
        ok = t == c["should_fallback"]
        rows.append(f"| {i} | {c['should_fallback']} | {t} | {ok} | {c['query'][:42]} |")

    md = [
        "# Fallback trigger eval",
        "",
        f"- cases where fallback SHOULD fire: {len(should)}",
        f"- trigger rate when it should: **{rate:.3f}**",
        f"- hold rate when it should NOT: **{hold:.3f}**",
        "",
        *rows,
        "",
    ]
    OUT.write_text("\n".join(md))
    (ROOT / "metrics_fallback.json").write_text(
        json.dumps(
            {
                "trigger_rate_should": rate,
                "hold_rate_should_not": hold,
                "should_count": len(should),
                "cases": len(cases),
            },
            indent=2,
        )
    )
    print("\n".join(md))

if __name__ == "__main__":
    main()
