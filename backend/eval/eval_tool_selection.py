import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from tools import select_tool

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv()

ROOT = Path(__file__).parent
TS = ROOT / "testsets" / "tool_selection.json"
OUT = ROOT / "results_tool_selection.md"


def main():
    cases = json.loads(TS.read_text())
    ok = 0
    soft = 0
    rows = ["| # | gold | pred | ok | soft | incident |", "|---|---|---|---|---|---|"]

    for i, c in enumerate(cases, 1):
        pick = select_tool(c["incident"])
        pred = pick.tool_name
        hit = pred == c["correct_tool"]
        alt = c.get("also_plausible") or []
        soft_hit = hit or pred in alt
        if hit:
            ok += 1
        if soft_hit:
            soft += 1
        rows.append(
            f"| {i} | {c['correct_tool']} | {pred} | {hit} | {soft_hit} | {c['incident'][:42]} |"
        )

    acc = ok / len(cases) if cases else 0.0
    soft_acc = soft / len(cases) if cases else 0.0
    md = [
        "# Tool selection eval",
        "",
        f"- cases: {len(cases)}",
        f"- accuracy (exact preferred tool): **{acc:.3f}**",
        f"- soft accuracy (preferred or also_plausible): **{soft_acc:.3f}**",
        "",
        *rows,
        "",
    ]
    OUT.write_text("\n".join(md))
    (ROOT / "metrics_tool_selection.json").write_text(
        json.dumps(
            {
                "accuracy": acc,
                "soft_accuracy": soft_acc,
                "cases": len(cases),
            },
            indent=2,
        )
    )
    print("\n".join(md))


if __name__ == "__main__":
    main()
