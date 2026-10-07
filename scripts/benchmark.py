#!/usr/bin/env python3
"""Collect one iteration's code-graded runs into a receipts file.

Usage: scripts/benchmark.py <skill> --iteration N --tools "mock shell tool" [--note TEXT]

Reads every run under skills/<skill>-workspace/iteration-N/ that evals/check.py
has graded and writes skills/<skill>/evals/results/<today>-benchmark.json:
each run's grade and evidence, plus totals per configuration.
"""
import argparse
import datetime
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ("with_skill", "without_skill")


def spread(values):
    return {"mean": round(statistics.mean(values), 4), "stddev": round(statistics.pstdev(values), 4), "min": min(values), "max": max(values)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill")
    ap.add_argument("--iteration", type=int, required=True)
    ap.add_argument("--tools", required=True, help="what the agent ran against, for the record")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--note", action="append", default=[])
    args = ap.parse_args()

    evals = {e["name"]: e for e in json.loads((ROOT / "skills" / args.skill / "evals" / "evals.json").read_text())["evals"]}
    ws = ROOT / "skills" / f"{args.skill}-workspace" / f"iteration-{args.iteration}"
    runs = []
    for grading in sorted(ws.glob("eval-*/*/run-*/grading.json")):
        name, config, number = grading.parts[-4][5:], grading.parts[-3], int(grading.parts[-2][4:])
        graded = json.loads(grading.read_text())
        timing = json.loads((grading.parent / "timing.json").read_text())
        checks = json.loads((grading.parent / "checks.json").read_text())
        runs.append({"eval_id": evals[name]["id"], "eval_name": name, "configuration": config, "run_number": number,
                     "result": {**{k: graded["summary"][k] for k in ("pass_rate", "passed", "failed", "total")},
                                "time_seconds": timing["total_duration_seconds"], "tokens": timing["total_tokens"],
                                "cost_usd": timing["cost_usd"], "errors": 1 if checks["agent_error"] else 0},
                     "expectations": graded["expectations"], "notes": []})
    per = {len([r for r in runs if r["eval_name"] == n and r["configuration"] == c]) for n in evals for c in CONFIGS}
    if len(per) != 1 or 0 in per:
        raise SystemExit(f"uneven or missing runs per scenario and configuration: {sorted(per)}")
    summary = {}
    for config in CONFIGS:
        results = [r["result"] for r in runs if r["configuration"] == config]
        summary[config] = {"passed": sum(r["passed"] for r in results), "total": sum(r["total"] for r in results),
                           **{k: spread([r[k] for r in results]) for k in ("pass_rate", "time_seconds", "tokens", "cost_usd")}}
    now = datetime.datetime.now(datetime.timezone.utc)
    out = {"metadata": {"skill_name": args.skill, "skill_path": f"skills/{args.skill}",
                        "executor_model": f"{args.model} (claude -p --restricted, {args.tools})",
                        "analyzer_model": "none: graded by evals/check.py", "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "evals_run": sorted(e["id"] for e in evals.values()), "runs_per_configuration": per.pop()},
           "runs": runs, "run_summary": summary, "notes": args.note}
    target = ROOT / "skills" / args.skill / "evals" / "results" / f"{now:%Y-%m-%d}-benchmark.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    for config in CONFIGS:
        print(f"{config}: {summary[config]['passed']}/{summary[config]['total']}, mean ${summary[config]['cost_usd']['mean']:.3f} per run")
    print(f"written: {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
