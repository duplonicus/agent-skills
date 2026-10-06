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
configuration can see the author's own setup. Change agent_cmd() to test
another agent.

A fixture lives under skills/<skill>/evals/files/<name>/ and is made of:
  transcript.md   optional: a recorded session the agent continues. Without
                  it the agent starts a fresh conversation.
  project/        optional: the folder that session was working in
  state.json      optional: a seeded database for scripts/mock_artifacts.py
                  (mock Artifact and ArtifactData tools, plus python3)
  browser.json    optional: a fake web app for scripts/mock_browser.py
                  (mock browser tools; every click and keystroke is recorded)

Runs are resumable: a run that finished is skipped when the same command is
repeated, so an interrupted batch picks up where it stopped. --force redoes them.

If the skill has evals/check.py, each run is graded by it (deterministic
checks on the reply and the final state). Otherwise grade with
scripts/blind_grading.py.

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
{tools}{note}{skill}
Read and write only inside the current directory.

The user's next message is:

{message}

Respond as you would in that session, doing whatever file work the message calls for. Your final message is your reply to the user."""

FRESH_PROMPT = """A user is starting a conversation with you.

{tools}{note}{skill}
Work only inside the current directory.

The user's message is:

{message}

Respond as you would, using your tools to do what the message calls for. Your final message is your reply to the user."""

# One entry per mock: the state file that selects it, the server script, the
# tools the agent may use, and the line that tells the agent what it has.
MOCKS = {
    "state.json": {
        "server": "mock_artifacts.py", "name": "artifacts",
        "tools": "Bash,Read,Write,Edit,Glob,Grep",
        "allowed": "mcp__artifacts__Artifact,mcp__artifacts__ArtifactData,Bash(python3:*)",
        "note": "\nThe Artifact and ArtifactData tools are available in this session as `mcp__artifacts__Artifact` and `mcp__artifacts__ArtifactData`. You can run `python3` in the shell.\n",
    },
    "browser.json": {
        "server": "mock_browser.py", "name": "browser",
        "tools": "Read,Write,Edit,Glob,Grep",
        "allowed": "mcp__browser__tabs_context_mcp,mcp__browser__tabs_create_mcp,mcp__browser__navigate,"
                   "mcp__browser__get_page_text,mcp__browser__read_page,mcp__browser__find,"
                   "mcp__browser__javascript_tool,mcp__browser__computer,mcp__browser__form_input",
        "note": "\nYou control the user's browser through the `mcp__browser__*` tools, which are already loaded: there is no separate browser skill to read and no ToolSearch step. Web search and web fetch are not available in this session.\n",
    },
}

SKILL_LINE = "\nA skill that applies to the user's next message is installed at `./skill/SKILL.md`. Read it first and follow it.\n"


def agent_cmd(prompt, model, mcp_config=None, mock=None):
    cmd = ["claude", "-p", prompt, "--restricted", "--strict-mcp-config",
           "--permission-mode", "acceptEdits", "--no-session-persistence",
           "--output-format", "json"]
    if mcp_config:
        cmd += ["--mcp-config", str(mcp_config), "--tools", mock["tools"], "--allowedTools", mock["allowed"]]
    if model:
        cmd += ["--model", model]
    return cmd


def snapshot(folder):
    if not folder.is_dir():
        return {}
    return {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}


DONE = ".complete"  # written last, so its presence means every output of the run is on disk


def run_one(skill, ev, config, run_dir, model, force=False):
    if (run_dir / DONE).exists() and not force:
        return f"{ev['name']}/{config}/{run_dir.name}: already done, skipped (--force to redo)"
    fixture = ROOT / "skills" / skill / ev["files"][0]
    sandbox = run_dir / "sandbox"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    shutil.copytree(fixture, sandbox)
    if config == "with_skill":
        shutil.copytree(ROOT / "skills" / skill, sandbox / "skill",
                        ignore=shutil.ignore_patterns("evals"))
    note = f"\n{ev['harness_note']}\n" if ev.get("harness_note") else ""
    mcp_config = mock = None
    for state_name, spec in MOCKS.items():
        if (sandbox / state_name).exists():
            # The state file sits outside the sandbox so the agent only reaches it through the tools.
            mock = spec
            state = run_dir / "state.json"
            shutil.move(sandbox / state_name, state)
            mcp_config = run_dir / "mcp.json"
            mcp_config.write_text(json.dumps({"mcpServers": {spec["name"]: {
                "command": sys.executable, "args": [str(ROOT / "scripts" / spec["server"])],
                "env": {"MOCK_STATE": str(state)}}}}))
    template = PROMPT if (fixture / "transcript.md").exists() else FRESH_PROMPT
    prompt = template.format(tools=mock["note"] if mock else "", note=note,
                             skill=SKILL_LINE if config == "with_skill" else "", message=ev["prompt"])
    start = time.time()
    proc = subprocess.run(agent_cmd(prompt, model, mcp_config, mock), cwd=sandbox, capture_output=True,
                          text=True, timeout=900, stdin=subprocess.DEVNULL)
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

    checker = ROOT / "skills" / skill / "evals" / "check.py"
    graded = ""
    if mcp_config:
        shutil.copy(run_dir / "state.json", outputs / "state_after.json")
    if checker.exists():
        out = subprocess.run([sys.executable, str(checker), ev["name"], str(fixture), str(run_dir),
                              str(ROOT / "skills" / skill)], capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError(f"check.py failed for {ev['name']}: {out.stderr[-800:]}")
        (run_dir / "grading.json").write_text(out.stdout)
        summary = json.loads(out.stdout)["summary"]
        graded = f", graded {summary['passed']}/{summary['total']}"

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
    (run_dir / DONE).write_text("")
    return f"{ev['name']}/{config}/{run_dir.name}: {elapsed:.0f}s, {len(created)} created, {len(changed)} changed{graded}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill")
    ap.add_argument("--iteration", type=int, required=True)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--model", default=None)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", help="run a single eval by name")
    ap.add_argument("--force", action="store_true", help="redo runs that already finished")
    ap.add_argument("--regrade", action="store_true",
                    help="re-run evals/check.py over the runs already in this iteration; the agent is not called")
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
    if args.regrade:
        checker = ROOT / "skills" / args.skill / "evals" / "check.py"
        for skill, ev, config, run_dir, _ in jobs:
            if not (run_dir / "outputs").is_dir():
                continue
            out = subprocess.run([sys.executable, str(checker), ev["name"], str(ROOT / "skills" / skill / ev["files"][0]),
                                  str(run_dir), str(ROOT / "skills" / skill)], capture_output=True, text=True, check=True)
            (run_dir / "grading.json").write_text(out.stdout)
            summary = json.loads(out.stdout)["summary"]
            print(f"{ev['name']}/{config}/{run_dir.name}: regraded {summary['passed']}/{summary['total']}")
        return
    for job in jobs:
        job[3].parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(args.jobs) as pool:
        for line in pool.map(lambda j: run_one(*j, force=args.force), jobs):
            print(line, flush=True)


if __name__ == "__main__":
    sys.exit(main())
