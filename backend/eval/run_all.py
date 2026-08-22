import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

SCRIPTS = [
    "eval_retrieval.py",
    "eval_grading.py",
    "eval_fallback.py",
    "eval_tool_selection.py",
    "eval_guardrails.py",
    "eval_faithfulness.py",
]

# (metric_key, label, compare, threshold, metrics_file)
# compare: "gte" | "lte" | "near0"
CHECKS = [
    ("recall_at_3", "Retrieval Recall@3 (fresh seed)", "gte", 0.80, "metrics_retrieval.json"),
    ("stale_recall", "Retrieval Recall on stale (not ingested)", "near0", 0.15, "metrics_retrieval.json"),
    ("false_positive_rate", "Grading false-positive rate", "lte", 0.10, "metrics_grading.json"),
    ("trigger_rate_should", "Fallback trigger accuracy", "gte", 0.85, "metrics_fallback.json"),
    ("accuracy", "Tool selection accuracy", "gte", 0.80, "metrics_tool_selection.json"),
    ("input_catch_rate", "Input guardrail catch rate", "gte", 0.90, "metrics_guardrails.json"),
    ("output_catch_rate", "Output guardrail catch rate", "gte", 0.85, "metrics_guardrails.json"),
    ("output_false_flag_rate", "Output guardrail false-flag rate", "lte", 0.15, "metrics_guardrails.json"),
    ("mean_faithful_score", "Faithfulness mean (1-5, grounded cases)", "gte", 4.0, "metrics_faithfulness.json"),
]


def passes_threshold(val, compare, thr):
    if compare == "gte":
        return val >= thr
    if compare == "lte":
        return val <= thr
    if compare == "near0":
        return val <= thr
    return False


def main():
    for name in SCRIPTS:
        print(f"\n=== {name} ===")
        r = subprocess.run([sys.executable, str(ROOT / name)], cwd=str(ROOT.parent))
        if r.returncode != 0:
            print(f"failed: {name} exit={r.returncode}")
            sys.exit(r.returncode)

    cache = {}
    rows = [
        "| metric | result | threshold | status |",
        "|---|---|---|---|",
    ]
    fails = 0
    notes = []

    for key, label, compare, thr, fname in CHECKS:
        if fname not in cache:
            cache[fname] = json.loads((ROOT / fname).read_text())
        m = cache[fname]
        val = float(m[key])
        ok = passes_threshold(val, compare, thr)
        if not ok:
            fails += 1
        status = "PASS" if ok else "FAIL"
        if compare == "gte":
            thr_s = f">= {thr}"
        elif compare == "lte":
            thr_s = f"<= {thr}"
        else:
            thr_s = f"~0 (expected miss, <= {thr})"
        rows.append(f"| {label} | {val:.3f} | {thr_s} | **{status}** |")

    faith = cache.get("metrics_faithfulness.json") or json.loads(
        (ROOT / "metrics_faithfulness.json").read_text()
    )
    low = faith.get("low_score_flags") or []
    if low:
        notes.append(f"- manual review: {len(low)} answer(s) scored <=2")
        for item in low:
            notes.append(f"  - score={item['score']}: {item['query'][:70]}")

    # stale near-0 is the point of the test — call that out
    notes.append(
        "- stale recall near 0 is expected (proves the moving-index check is real, not a bug)"
    )

    overall = "PASS" if fails == 0 else f"FAIL ({fails} metric(s) below threshold)"
    md = [
        "# Eval gate report",
        "",
        f"**Overall: {overall}**",
        "",
        *rows,
        "",
        "## Notes",
        "",
        *notes,
        "",
    ]
    out = ROOT / "results.md"
    out.write_text("\n".join(md))
    print("\n" + "\n".join(md))
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
