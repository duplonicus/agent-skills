# agent-skills

Three skills I wrote and use, in the open [Agent Skills](https://agentskills.io) format: a folder with a `SKILL.md` that any compatible agent can load.

| Skill | What it does |
|---|---|
| [`guided-tour`](skills/guided-tour/SKILL.md) | Teaches someone a web app live in their own browser. The agent navigates and spotlights each control, explains it, sets a small try-it task, then stops and waits at every stop. The user makes every click that changes anything. |
| [`sum`](skills/sum/SKILL.md) | End-of-session handoff. Writes the current state to `NOW.md` and one line to `LOG.md`, so the next session on any agent or machine continues without re-reading the conversation. |
| [`critique`](skills/critique/SKILL.md) | Honest post-mortem of a session: the agent's own process mistakes and the work product as its reader will see it, with evidence, ending in rules for next time. |

## guided-tour

Most agent tooling is built to finish a task alone. This one is built to stop.

A person learns a UI by touching it, so the tour is a loop of *point, explain, try it, wait*:

- **One stop per turn.** Each stop names the control, says what real job it does, gives one small read-only task, and ends the turn. The user explores and asks questions for as long as they like.
- **A spotlight, not a screenshot.** [`scripts/spotlight.js`](skills/guided-tour/scripts/spotlight.js) outlines the control and tags it with the stop number. It reaches into same-origin iframes and open shadow roots, restores the page's own styles when cleared, and never clicks or types.
- **The agent points, the user acts.** Anything that creates, changes, deletes, sends or costs money is the user's click, after the agent has said what it does and what it bills. Sign-in, consent screens and cookie banners are always theirs.
- **Live page over docs, docs over memory.** Admin consoles get redesigned often, so the outline is checked against the vendor's current docs and then against what is on screen.
- **Somewhere safe to practise.** [`references/practice-environments.md`](skills/guided-tour/references/practice-environments.md) lists where to find a safe sandbox for each kind of tool, and tells the agent to quote the vendor's current terms instead of recalling them.

It needs an agent with browser tools that can read the open page and run JavaScript in it.

## sum and critique

Both are small on purpose. What they add over a capable agent with no skill is consistency: the same files, the same shape, the same rules every time.

`sum` rests on two files with different jobs. `NOW.md` is overwritten, so it is always the current truth and never grows. `LOG.md` is append-only, one line per session. The skill's rules are the ones that bite in practice: read the existing state first so another session's open items survive, write only what was observed ("14 passed, 1 failed, not re-run" instead of "tests pass"), use absolute dates, and keep secrets out.

`critique` asks for evidence behind every finding (a quote or a file and line), scales to what happened so a clean session gets a short answer, and reports without fixing: the user decides what is worth acting on.

## Evals

`sum` and `critique` each ship with three recorded sessions in `skills/<name>/evals/`: a transcript, the project folder that session was working in, and a list of plain-language expectations.

Each scenario was run with the skill and without it, three times each, and graded blind:

| Skill | With the skill | No skill | Where the gap is |
|---|---|---|---|
| `sum` | 72 / 72 | 66 / 72 | All six misses are about the reply: it should be short and end with the line that starts the next session. |
| `critique` | 72 / 72 | 55 / 72 | 14 of the 17 misses are in the coding post-mortem: no one-line verdict, no evidence table, no rules. |

Counts are expectations passed, summed over 3 scenarios x 3 runs. Measured 2026-10-05 on Claude Opus 5.5 through `claude -p --restricted`, which hides the author's own settings and instruction files from both configurations. The grader was a separate agent session that could not see which configuration produced a run. Per-run grades and evidence are in `skills/<name>/evals/results/`.

Read these numbers with their limits:

- **They measure consistency more than insight.** I wrote the expectations, and several check the skill's own output shape. With no skill the model still caught the main problems in every scenario: the untested "tests pass", the open item from another session, the cover letter's 400 that should have been 40.
- **Three scenarios per skill, one model.** The grader also flagged expectations that passed for every run in both configurations, so they separate nothing.
- **The skills cost a little more.** Mean cost per run was $0.138 with `sum` against $0.123 without, and $0.134 with `critique` against $0.098 without.

The evals did change one skill. In the first round `critique` padded a clean session with marginal findings and scored 4 of 6 there on its single run; a section on proportion fixed it (18 of 18 over three runs).

`guided-tour` needs a live browser and a person at every stop, so it has no automated evals here.

To reproduce (needs the `claude` CLI; swap the command in `scripts/run_evals.py` to test another agent):

```bash
scripts/run_evals.py sum --iteration 1 --runs 3
scripts/blind_grading.py pack sum --iteration 1
# a grader writes grading.json into each anonymous packet, then:
scripts/blind_grading.py unpack sum --iteration 1
```

## Install

Copy a skill's folder to wherever your agent loads skills from. For Claude Code that is `~/.claude/skills/`:

```bash
git clone https://github.com/duplonicus/agent-skills
cp -r agent-skills/skills/guided-tour ~/.claude/skills/
```

Each folder is self-contained. Leave out `evals/` if you only want the skill.

## Validate

```bash
scripts/validate.sh
```

Runs the spec's reference validator ([skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref)) over every skill. Needs [uv](https://docs.astral.sh/uv/).

## License

MIT
