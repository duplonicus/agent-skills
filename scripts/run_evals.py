#!/usr/bin/env python3
"""Run a skill's evals with and without the skill, in isolated agent sessions.

Each eval is a recorded session (transcript.md) plus the project folder that
session was working in. The runner copies both into a throwaway sandbox, starts
a fresh headless agent there, hands it the user's next message, and collects the
reply and every file the agent created or changed.

Two configurations per eval:
  with_skill     the agent is told to read and follow the skill
  without_skill  same prompt, no skill (the baseline)

Runs use `claude -p --restricted`, which ignores user/project settings and
instruction files and confines file tools to the sandbox, so neither
configuration can see the author's own setup. Swap AGENT_CMD to test another
agent.

Usage:
    scripts/run_evals.py sum --iteration 1 [--runs 1] [--model MODEL] [--jobs 4]

Output layout (the one skill-creator's aggregator and viewer expect):
    skills/<skill>-workspace/iteration-N/eval-<name>/<config>/run-K/
        outputs/        reply.md plus changed/created project files (flattened)
        checks.json     deterministic facts about the run, for grading
        timing.json     duration, tokens, cost
"""
import argparse
import filecmp
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ("with_skill", "without_skill")

PROMPT = """You are partway through a working session with a user.

`transcript.md` in the current directory is the conversation so far. Read it and treat it as your own history in this session. The session's project folder is `./project`.
{note}{skill}
Read and write only inside the current directory.

The user's next message is:

{message}

Respond as you would in that session, doing whatever file work the message calls for. Your final message is your reply to the user."""

SKILL_LINE = "\nA skill that applies to the user's next message is installed at `./skill/SKILL.md`. Read it first and follow it.\n"


def agent_cmd(prompt, model):
    cmd = ["claude", "-p", prompt, "--restricted", "--strict-mcp-config",
           "--permission-mode", "acceptEdits", "--no-session-persistence",
           "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    return cmd


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}


def run_one(skill, ev, config, run_dir, model):
    fixture = ROOT / "skills" / skill / ev["files"][0]
    sandbox = run_dir / "sandbox"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    shutil.copytree(fixture, sandbox)
    if config == "with_skill":
        shutil.copytree(ROOT / "skills" / skill, sandbox / "skill",
                        ignore=shutil.ignore_patterns("evals"))
    note = f"\n{ev['harness_note']}\n" if ev.get("harness_note") else ""
    prompt = PROMPT.format(note=note, skill=SKILL_LINE if config == "with_skill" else "",
                           message=ev["prompt"])
    start = time.time()
    proc = subprocess.run(agent_cmd(prompt, model), cwd=sandbox, capture_output=True,
                          text=True, timeout=900)
    elapsed = time.time() - start
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result = {"result": "", "error": (proc.stdout + proc.stderr)[-2000:]}

    outputs = run_dir / "outputs"
    outputs.mkdir()
    reply = result.get("result") or ""
    (outputs / "reply.md").write_text(reply)

    before = snapshot(fixture / "project")
    after = snapshot(sandbox / "project")
    created = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after)
                     if not filecmp.cmp(before[k], after[k], shallow=False))
    for rel in created + changed:
        shutil.copy(after[rel], outputs / rel.replace("/", "__"))

    usage = result.get("usage") or {}
    tokens = sum(usage.get(k, 0) for k in ("input_tokens", "output_tokens",
                 "cache_creation_input_tokens", "cache_read_input_tokens"))
    (run_dir / "timing.json").write_text(json.dumps({
        "total_tokens": tokens,
        "output_tokens": usage.get("output_tokens", 0),
        "duration_ms": int(elapsed * 1000),
        "total_duration_seconds": round(elapsed, 1),
        "cost_usd": result.get("total_cost_usd"),
        "num_turns": result.get("num_turns"),
    }, indent=2))
    (run_dir / "checks.json").write_text(json.dumps({
        "project_files_created": created,
        "project_files_changed": changed,
        "project_files_deleted": deleted,
        "reply_lines": len(reply.splitlines()),
        "reply_chars": len(reply),
        "agent_error": result.get("error") or (proc.stderr[-500:] if proc.returncode else None),
    }, indent=2))
    meta = {"eval_id": ev["id"], "eval_name": ev["name"], "prompt": ev["prompt"],
            "assertions": ev.get("expectations", [])}
    (run_dir / "eval_metadata.json").write_text(json.dumps(meta, indent=2))
    (run_dir.parent.parent / "eval_metadata.json").write_text(json.dumps(meta, indent=2))
    return f"{ev['name']}/{config}/{run_dir.name}: {elapsed:.0f}s, {len(created)} created, {len(changed)} changed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill")
    ap.add_argument("--iteration", type=int, required=True)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--model", default=None)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", help="run a single eval by name")
    args = ap.parse_args()

    evals = json.loads((ROOT / "skills" / args.skill / "evals" / "evals.json").read_text())["evals"]
    ws = ROOT / "skills" / f"{args.skill}-workspace" / f"iteration-{args.iteration}"
    jobs = []
    for ev in evals:
        if args.only and ev["name"] != args.only:
            continue
        for config in CONFIGS:
            for k in range(1, args.runs + 1):
                jobs.append((args.skill, ev, config, ws / f"eval-{ev['name']}" / config / f"run-{k}", args.model))
    for job in jobs:
        job[3].parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(args.jobs) as pool:
        for line in pool.map(lambda j: run_one(*j), jobs):
            print(line, flush=True)


if __name__ == "__main__":
    sys.exit(main())
