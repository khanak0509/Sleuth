import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from guardrails import check_input, check_output

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv()

ROOT = Path(__file__).parent
TS = ROOT / "testsets" / "guardrails.json"
OUT = ROOT / "results_guardrails.md"


def main():
    data = json.loads(TS.read_text())
    inp = data["input"]
    out = data["output"]

    in_catch = 0
    in_block_cases = [c for c in inp if c["should_block"]]
    in_rows = ["| # | should_block | blocked | ok | query |", "|---|---|---|---|---|"]
    for i, c in enumerate(inp, 1):
        g = check_input(c["query"])
        blocked = not g.safe
        ok = blocked == c["should_block"]
        if c["should_block"] and blocked:
            in_catch += 1
        in_rows.append(
            f"| {i} | {c['should_block']} | {blocked} | {ok} | {c['query'][:46]} |"
        )
    in_rate = in_catch / len(in_block_cases) if in_block_cases else 0.0

    out_catch = 0
    out_false_flag = 0
    out_flag_cases = [c for c in out if c["should_flag"]]
    out_safe_cases = [c for c in out if not c["should_flag"]]
    out_rows = ["| # | should_flag | flagged | ok | answer |", "|---|---|---|---|---|"]
    for i, c in enumerate(out, 1):
        g = check_output(c["answer"])
        flagged = not g.safe
        ok = flagged == c["should_flag"]
        if c["should_flag"] and flagged:
            out_catch += 1
        if (not c["should_flag"]) and flagged:
            out_false_flag += 1
        out_rows.append(
            f"| {i} | {c['should_flag']} | {flagged} | {ok} | {c['answer'][:46]} |"
        )
    out_rate = out_catch / len(out_flag_cases) if out_flag_cases else 0.0
    false_flag_rate = (
        out_false_flag / len(out_safe_cases) if out_safe_cases else 0.0
    )

    md = [
        "# Guardrail eval",
        "",
        f"- input catch rate (should_block): **{in_rate:.3f}** ({in_catch}/{len(in_block_cases)})",
        f"- output catch rate (should_flag): **{out_rate:.3f}** ({out_catch}/{len(out_flag_cases)})",
        f"- output false-flag rate (safe wrongly flagged): **{false_flag_rate:.3f}** ({out_false_flag}/{len(out_safe_cases)})",
        "",
        "## Input",
        "",
        *in_rows,
        "",
        "## Output",
        "",
        *out_rows,
        "",
    ]
    OUT.write_text("\n".join(md))
    (ROOT / "metrics_guardrails.json").write_text(
        json.dumps(
            {
                "input_catch_rate": in_rate,
                "output_catch_rate": out_rate,
                "output_false_flag_rate": false_flag_rate,
                "input_block_cases": len(in_block_cases),
                "output_flag_cases": len(out_flag_cases),
                "output_safe_cases": len(out_safe_cases),
            },
            indent=2,
        )
    )
    print("\n".join(md))


if __name__ == "__main__":
    main()
