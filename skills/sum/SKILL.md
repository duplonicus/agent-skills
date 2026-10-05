---
name: sum
description: End-of-session handoff. Writes where the work stands into two plain files in the project, NOW.md (overwritten with the current state) and LOG.md (one line appended), so the next session on any agent, surface or machine picks up exactly where this one stopped without re-reading the conversation. Use on /sum, and whenever the user is wrapping up, switching sessions or machines, running low on context, or asks for a handoff, a session summary, "save where we are", "write this down for next time" or "so I can pick this up later", even if they never say "sum". Falls back to a paste-ready summary block when the session cannot write files.
license: MIT
metadata:
  author: duplonicus
  version: "1.0"
---

# /sum

Goal: zero context drift. The next session should continue from exactly here without re-reading this conversation and without the user explaining anything twice.

State goes in files rather than in a chat message because files are the one thing every later session can reach, whichever agent, surface or machine it runs on. A summary pasted into chat is gone the moment the thread is.

## The two files

- **`NOW.md` is the current state.** It is overwritten every time, so it never grows and never contradicts itself. A new session reads this one file and knows where things stand.
- **`LOG.md` is the history.** It is append-only, one line per session, newest at the bottom. It answers "when did we do that?" without bloating NOW.md.

## Where they live

Use the first of these that applies:

1. **The user's standing instructions name a location** (an `AGENTS.md`, `CLAUDE.md` or similar instruction file, saved memory, or something they said in this session). Use it exactly, including any line format they specify.
2. **State files already exist** in the project (`NOW.md` and `LOG.md` at the project root or in a docs folder). Keep using them where they are.
3. **Neither.** Create `NOW.md` and `LOG.md` at the project root (the repository top level, or the working directory when there is no repository) and say in your reply that you created them.

Some users also keep an **index**: one `NOW.md` above several projects with a row per project. If one exists, touch it only when a project was added, its one-line status changed, or a cross-project item changed.

## Steps

1. **Read the existing state files first.** Another session may have written to them since this one started. Whatever they say that this session did not make obsolete has to survive your rewrite. Losing someone else's open item is the worst thing this skill can do.

2. **Check the claims you are about to write.** NOW.md is read as fact by a session that cannot ask you questions. For each claim about state (tests passing, deployed, committed, sent, merged), write what you actually observed this session. If a thing was planned or attempted but not confirmed, say so in those words ("not run", "unverified", "failed with ..."). A handoff that says "tests pass" when one still fails costs the next session more than no handoff at all.

3. **Rewrite NOW.md** (overwrite, never append). Facts only, under about 40 lines, with these sections:

   ```markdown
   # NOW: <project>

   **Updated:** <absolute date, plus the time if you know it> by <agent and surface>

   ## State
   What is true right now: what works, what is broken, what is running,
   branch and uncommitted work, versions, ports.

   ## Where things live
   Every path, URL, ID, draft, scheduled job or open tab a new session
   would otherwise have to hunt for.

   ## Next
   1. Ordered by priority. Include anything mentioned but not finished.

   ## Gotchas
   Non-obvious decisions and pitfalls from this session.
   ```

   - Write dates as absolute dates. "Tomorrow" and "last week" are meaningless to a session that starts on a different day.
   - "Next" carries forward every unfinished item: this session's, plus any from the old NOW.md that are still open.
   - "Gotchas" holds what the next session could not work out from the code or the instruction file, such as why an approach was abandoned or a trap that cost time. Skip anything those files already record.

4. **Append one line to LOG.md.** Use the format already in the file. If the file is new, use:

   ```
   - YYYY-MM-DD · <agent and surface> · <project> · <what happened, one line>
   ```

   Never edit or reorder the lines already there.

5. **Update the index**, if there is one, only when something on it changed.

6. **Keep secrets out.** Passwords, tokens, API keys, client secrets and card or account numbers never go into these files, even when they appeared in the conversation. The files get committed, synced and read by other tools. Record where the secret is stored (for example "API token is in `.env`"), never its value.

7. **Reply in two to four lines:** which files you wrote, anything you could not verify, and the line that starts the next session, in a code block:

   ```
   Read <path to NOW.md> and continue.
   ```

   Then stop. Do not restate the summary in chat (it is in the file) and do not add sign-off advice.

## Fallback: the session cannot write files

In a chat surface with no file access, or when the project folder is not reachable, produce the handoff as one fenced Markdown block the user can paste as the first message of the next thread:

```markdown
## Session summary: <absolute date>

### What we did
Completed work, specific: file names, function names, commands run, results.

### Current state
One short paragraph on what is true right now.

### Open / next
1. Ordered by priority.

### Key decisions and gotchas
Non-obvious choices and pitfalls.

### Files and links
Everything touched or created: files, docs, drafts, scheduled jobs, URLs, IDs.
```

The same rules apply: under about 40 lines, facts only, unverified claims labelled, no secrets. After the block, add one line telling the user which state files to update from it once a session can reach the project.
