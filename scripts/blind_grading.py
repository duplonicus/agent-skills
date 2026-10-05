#!/usr/bin/env python3
"""Blind grading for eval runs.

`pack` copies every run of an iteration into an anonymous packet (r01, r02, ...)
in shuffled order, with the run's outputs, the deterministic checks, the session
transcript, the untouched project fixture and the expectations to grade. The
grader never sees which configuration produced a run. `unpack` copies each
packet's grading.json back to its run directory.

Usage:
    scripts/blind_grading.py pack   <skill> --iteration N
    scripts/blind_grading.py unpack <skill> --iteration N
"""
import argparse
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("pack", "unpack"))
    ap.add_argument("skill")
    ap.add_argument("--iteration", type=int, required=True)
    args = ap.parse_args()

    skill_dir = ROOT / "skills" / args.skill
    ws = ROOT / "skills" / f"{args.skill}-workspace"
    it = ws / f"iteration-{args.iteration}"
    packets = ws / "grading-packets" / f"iteration-{args.iteration}"
    map_file = ws / "grading-packets" / f"iteration-{args.iteration}.map.json"
    evals = {e["name"]: e for e in json.loads((skill_dir / "evals" / "evals.json").read_text())["evals"]}

    if args.action == "pack":
        runs = sorted(p.parent for p in it.glob("eval-*/*/run-*/outputs"))
        random.Random(f"{args.skill}-{args.iteration}").shuffle(runs)
        if packets.exists():
            shutil.rmtree(packets)
        mapping = {}
        for i, run in enumerate(runs, 1):
            rid = f"r{i:02d}"
            ev = evals[run.parent.parent.name.removeprefix("eval-")]
            fixture = skill_dir / ev["files"][0]
            dest = packets / rid
            shutil.copytree(run / "outputs", dest / "outputs")
            shutil.copy(run / "checks.json", dest / "checks.json")
            shutil.copy(fixture / "transcript.md", dest / "transcript.md")
            shutil.copytree(fixture / "project", dest / "original_project")
            (dest / "task.json").write_text(json.dumps({
                "user_message": ev["prompt"],
                "expectations": ev["expectations"],
            }, indent=2, ensure_ascii=False))
            mapping[rid] = str(run.relative_to(ws))
        map_file.write_text(json.dumps(mapping, indent=2))
        print(f"packed {len(runs)} runs into {packets}")
        return 0

    mapping = json.loads(map_file.read_text())
    bad = 0
    for rid, rel in mapping.items():
        src = packets / rid / "grading.json"
        if not src.exists():
            print(f"missing: {rid}")
            bad += 1
            continue
        g = json.loads(src.read_text())
        want = json.loads((packets / rid / "task.json").read_text())["expectations"]
        exps = g.get("expectations", [])
        if [e.get("text") for e in exps] != want or not all(
                isinstance(e.get("passed"), bool) and e.get("evidence") for e in exps):
            print(f"malformed: {rid}")
            bad += 1
            continue
        passed = sum(e["passed"] for e in exps)
        g["summary"] = {"passed": passed, "failed": len(exps) - passed, "total": len(exps),
                        "pass_rate": round(passed / len(exps), 4)}
        (ws / rel / "grading.json").write_text(json.dumps(g, indent=2, ensure_ascii=False))
    print(f"unpacked {len(mapping) - bad} of {len(mapping)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
