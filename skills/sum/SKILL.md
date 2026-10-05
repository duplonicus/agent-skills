---
name: sum
description: End-of-session handoff. Produces one paste-ready summary block (what was done, current state, what is next, gotchas, files touched) that the user drops in as the first message of the next thread, so a fresh session continues from exactly here without re-reading this one. Use on /sum, and whenever the user is wrapping up, starting a new chat, switching machines or agents, running low on context, or asks for a handoff, a session summary, "save where we are" or "so I can pick this up later", even if they never say "sum". Not for summarising a document or an article.
license: MIT
metadata:
  author: duplonicus
  version: "2.0"
---

# /sum

Goal: zero context drift. The next session should continue from exactly here without re-reading this conversation and without the user explaining anything twice.

The reader is an agent that starts cold. It cannot ask you what you meant, it will take every line as fact, and it will act on what it reads. Write for that reader.

## Output

One fenced Markdown block, so it copies in a single click, with these sections:

```markdown
## Session summary: <absolute date>

### What we did
Completed work, specific: file names, function names, commands run, results.

### Current state
One short paragraph on what is true right now.

### Open / next
1. Ordered by priority. Everything mentioned but not finished.

### Key decisions and gotchas
Non-obvious choices and pitfalls the next session must know.

### Files touched
Every file read, edited or created, plus links, IDs, drafts and scheduled jobs.
```

Keep the block under about 40 lines. Outside it, write at most two lines: anything the user must do before the next session, or nothing at all. Do not repeat the summary in prose around the block, and do not add sign-off advice.

## What makes a handoff trustworthy

- **Write what was observed, not what was intended.** For every claim about state (tests passing, deployed, committed, sent), give the last thing actually seen this session. If something was changed but not re-checked, say so in those words: "fixture added, suite not re-run; last run was 14 passed, 1 failed". A handoff that says "tests pass" when one still fails costs the next session more than no handoff.
- **Carry every loose end.** "Open / next" includes this session's unfinished work, anything the user mentioned in passing ("we should also..."), and open items raised earlier that nobody closed. The thing most often lost in a handoff is the task that was not this session's focus.
- **Keep the constraints attached to the steps.** "Import the list" is wrong if the user said "not until DNS is verified". Order and conditions are part of the task.
- **Use absolute dates.** "Tomorrow" and "next Tuesday" mean something else by the time the block is read. Convert them, and keep the user's original deadline wording if it carried a condition.
- **Flag what is unconfirmed.** A number the user wants to double-check, or an assumption nobody verified, is labelled as such next to where it appears.
- **Explain abandoned approaches.** If something was tried and dropped, say why in one line, so the next session does not try it again.
- **Leave secrets out.** Passwords, tokens, API keys and account numbers never go in the block, even when they appeared in the conversation. The block gets pasted into new threads and saved in notes. Say where the secret is stored ("token is in `.env`"), never its value.
- **Skip what is already written down.** Anything in the project's instruction file or README does not need repeating. Facts only, no commentary on how the session went.

## If the user keeps handoffs somewhere

Some users have standing instructions about where session notes go (a line in an `AGENTS.md` or `CLAUDE.md`, a notes file, a memory system). When they do, save the same summary there as they describe, and still show the block in the reply. Without such instructions, write no files: the block is the deliverable.
