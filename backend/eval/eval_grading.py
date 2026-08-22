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
TS = ROOT / "testsets" / "grading.json"
OUT = ROOT / "results_grading.md"

class Grade(BaseModel):
    relevant: bool
    reason: str

def grade_one(llm, query, docs):
    blob = "\n".join(docs)
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

    tp = fp = tn = fn = 0
    rows = ["| # | query | gold | pred | ok |", "|---|---|---|---|---|"]

    for i, c in enumerate(cases, 1):
        g = grade_one(llm, c["query"], c["docs"])
        gold = c["correct_relevant"]
        pred = g.relevant
        ok = pred == gold
        if gold and pred:
            tp += 1
        elif (not gold) and pred:
            fp += 1
        elif (not gold) and (not pred):
            tn += 1
        else:
            fn += 1
        rows.append(
            f"| {i} | {c['query'][:40]} | {gold} | {pred} | {ok} |"
        )

    neg = fp + tn
    fpr = fp / neg if neg else 0.0
    acc = (tp + tn) / len(cases)

    md = [
        "# Grading eval",
        "",
        f"- cases: {len(cases)}",
        f"- accuracy: **{acc:.3f}**",
        f"- false-positive rate (pred relevant when not): **{fpr:.3f}**  ← dangerous failure",
        f"- confusion: tp={tp} fp={fp} tn={tn} fn={fn}",
        "",
        *rows,
        "",
    ]
    OUT.write_text("\n".join(md))
    (ROOT / "metrics_grading.json").write_text(
        json.dumps(
            {
                "accuracy": acc,
                "false_positive_rate": fpr,
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
                "cases": len(cases),
            },
            indent=2,
        )
    )
    print("\n".join(md))

if __name__ == "__main__":
    main()
