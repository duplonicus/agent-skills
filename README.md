# agent-skills

Four skills I wrote and use, in the open [Agent Skills](https://agentskills.io) format: a folder with a `SKILL.md` that any compatible agent can load.

| Skill | What it does |
|---|---|
| [`guided-tour`](skills/guided-tour/SKILL.md) | Teaches someone a web app live in their own browser. The agent navigates and spotlights each control, explains it, sets a small try-it task, then stops and waits at every stop. The user makes every click that changes anything. |
| [`todo-list`](skills/todo-list/SKILL.md) | Keeps shopping and to-do lists in a live page the user can tap on and the agent can edit from chat. Every change the agent makes is undoable from the page's History. |
| [`sum`](skills/sum/SKILL.md) | Short for summary. End-of-session handoff. One paste-ready block (what was done, current state, what is next, gotchas, files touched) that starts the next thread, so a fresh session continues without re-reading this one. |
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

## todo-list

One page holds the lists. The user edits it by hand; the agent edits the same data from chat ("put sponges on my hardware store list", "I'm out of milk"). The page redraws live either way.

- **The agent writes data, never the page.** Changes go through the page's database, so nothing the user typed on the page is ever overwritten by a republish.
- **Every change is undoable.** [`scripts/writes.py`](skills/todo-list/scripts/writes.py) builds each write together with its history entry, and each delete with a snapshot, so the page's Restore button works for the agent's changes too. Writes are pinned to the version that was read, so an edit made on the page a second earlier is not lost.
- **It asks when it should and acts when it can.** A list that plainly does not exist gets made. A name that might mean an existing list ("home depot" when there is a "Hardware" list) gets a question. An item never lands on a list the user did not name.
- **No duplicates.** Asking for something already on the list says so. Asking for something already checked off unchecks it.

It needs Claude's Artifact tools, which host the page and its database.

## sum and critique

Both are small on purpose. What they add over a capable agent with no skill is consistency: the same files, the same shape, the same rules every time.

`sum` writes for a reader that starts cold and takes every line as fact. Its rules are the ones that bite in practice: report what was observed ("14 passed, 1 failed, not re-run" instead of "tests pass"), carry every loose end including the ones that were not this session's focus, keep conditions attached to their steps, use absolute dates, and keep secrets out.

`critique` asks for evidence behind every finding (a quote or a file and line), scales to what happened so a clean session gets a short answer, and reports without fixing: the user decides what is worth acting on.

### Using them together

I use the pair to move to a fresh session when the context window fills up:

1. **`/critique`** while the whole session is still in view. The agent reviews its own work and proposes fixes and rules.
2. **"Yes, fix it."** The fixes land in this session, where the agent still has the context to make them.
3. **`/sum`** once the work is in its best state. The handoff describes the fixed version, not the flawed one. It comes back as a single code block.
4. **Copy the block** with the code block's copy button.
5. **New session.** Paste it as the first message and carry on.

The order matters. A summary written before the critique hands the next session problems it has no context to find.

## Evals

`sum` and `critique` each ship with three recorded sessions in `skills/<name>/evals/`: a transcript, the project folder that session was working in, and a list of plain-language expectations. `todo-list` ships with six seeded databases and is run against a local stand-in for the Artifact tools ([`scripts/mock_artifacts.py`](scripts/mock_artifacts.py)), so its evals check the data the agent actually left behind.

Each scenario was run with the skill and without it, three times each, and graded blind:

| Skill | With the skill | No skill | Where the gap is |
|---|---|---|---|
| `sum` | 90 / 90 | 72 / 90 | 15 of the 18 misses are shape: no paste-ready block, or a saved handoff over the length limit. The other 3 are a deadline left as "the 20th". One scenario showed no gap at all. |
| `critique` | 72 / 72 | 55 / 72 | 14 of the 17 misses are in the coding post-mortem: no one-line verdict, no evidence table, no rules. |
| `todo-list` | 93 / 93 | 68 / 93 | Substance. With no skill the agent wrote no history entry in any of the 12 runs that needed one, so those changes could not be undone from the page; on a new page it wrote the items into the HTML all 3 times; in 1 of 3 runs it guessed a list where it should have asked. |

Counts are expectations passed, summed over every scenario x 3 runs (3 scenarios for `sum` and `critique`, 6 for `todo-list`). Measured 2026-10-05 on Claude Opus 5.5 through `claude -p --restricted`, which hides the author's own settings and instruction files from both configurations. For `sum` and `critique` the grader was a separate agent session that could not see which configuration produced a run. `todo-list` is graded by code ([`evals/check.py`](skills/todo-list/evals/check.py)) from the final state of the database. Per-run grades and evidence are in `skills/<name>/evals/results/`.

Read these numbers with their limits:

- **They measure consistency more than insight.** I wrote the expectations, and several check the skill's own output shape. With no skill the model still caught the main problems in every scenario: the untested "tests pass", the side task nobody had started, the cover letter's 400 that should have been 40. A reply with no paste block also fails three `sum` expectations at once, which overstates that gap.
- **`todo-list` runs against a mock.** It follows the documented rules for versions and batches, but it is not the real service. The no-skill agent could read the existing history entries and copy their shape; it had no way to know a new page's layout, so that scenario only checks outcomes any design could meet.
- **Three to six scenarios per skill, one model.** The grader also flagged expectations that passed for every run in both configurations, so they separate nothing.
- **The skills cost a little more.** Mean cost per run was $0.125 with `sum` against $0.108 without, $0.134 with `critique` against $0.098 without, and $0.079 with `todo-list` against $0.054 without.

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

## Validate and test

```bash
scripts/validate.sh
uv run --with pytest pytest tests
```

Runs the spec's reference validator ([skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref)) over every skill. The tests cover the `todo-list` helper script: every change carries its history entry, every delete a restorable snapshot, every write to an existing document a version pin, and incomplete input fails before anything is printed. Both need [uv](https://docs.astral.sh/uv/).

## License

MIT
