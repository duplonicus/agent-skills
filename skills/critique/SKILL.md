---
name: critique
description: Honest, evidence-based post-mortem of the current session, or of one slice of it ("/critique", "/critique just the cover letter", "how did we do on the migration", "what went wrong tonight"). Reviews the agent's own process mistakes and the work product as its intended reader or user would see it, then turns the lessons into standing rules. Use whenever the user types /critique or asks for a review of how the session went, a retro, a post-mortem or "be honest, how did that go", even without the word critique. Not for reviewing a code diff for bugs, which is a code review.
license: MIT
metadata:
  author: duplonicus
  version: "1.0"
---

# /critique

A blunt review of how the work went, so the next session goes better.

The user wants the truth, not reassurance. A critique that only says nice things is useless, and one that invents problems to look thorough wastes their time. Owning your own mistakes is the point; grovelling is not.

## Scope

- **No argument:** critique the whole session.
- **An argument** ("only the cover letter", "just the deploy"): critique that slice and leave the rest out, even if you noticed problems elsewhere. The user narrowed it on purpose.

## Before writing

1. **Go back to the evidence.** Re-read the scoped part of the conversation and open every file it produced or changed. Memory of a session is a summary, and summaries flatter. Each finding needs a quote, a file and line, or a command result behind it.
2. **Check what you can.** If a finding depends on something checkable (did the tests run, was it committed, did the deadline pass), check it. If it cannot be checked from here, label the finding "unverified" in the table.
3. **Look for repeats.** If the project keeps lessons somewhere (an instruction file, a memory folder, a notes file), skim it. A mistake that was already written down as a rule and happened again is a more serious finding than a new one.
4. **Ask only if the answer changes the critique.** One round of questions at most, using a structured question tool if the agent has one: scope, whether wording is in or only process, whether the work is final or still a draft. Otherwise just write it.

## What to look for

- **Process mistakes.** Work wiped or overwritten, building before understanding the problem, patching the same symptom a third time instead of stepping back, effort out of proportion to the request, questions asked that the files already answered, problems surfaced late, stopping or winding the session down uninvited.
- **Claims that outran the evidence.** "Done", "fixed", "tests pass" or "verified" said without running the thing. A conclusion drawn from one example. A cause asserted from reading code, never from reproducing the failure.
- **Facts.** Anything invented, inflated or changed from how the user told it: numbers, dates, cause and effect, who did what. These do the most damage, because the user repeats them to someone else in good faith.
- **The work product, through its consumer's eyes.** Read a document the way its reader will (a recruiter skimming for 30 seconds, a client, a reviewer). Read code the way its next maintainer or its user will. Say what lands, what is weak, what is missing and what would get it rejected.
- **Wording.** Phrases that could hurt the user with that reader (hype, vague claims, walls of text), including wording the user asked for that you should have questioned and did not.
- **How the two of you worked.** Where a clearer request, an earlier check-in or a tool that went unused would have saved time. This cuts both ways; say so when the user's instruction was the cause.
- **What went well.** Short and specific. Only what is worth doing again on purpose.

If something was fine, say it was fine. Do not fill a table to make the critique look complete.

## Proportion

Match the size of the critique to what happened. A short session that went well gets a short critique: the verdict, the one real finding, a line or two on what to repeat, and usually no new rules. A session that lost work or sent out a wrong fact gets the full treatment.

Leave a section out when it would be empty or marginal. The test for any finding is whether the user would do something differently because they read it. If you would introduce it with "minor" or "nitpick", cut it: a long list of small points buries the one that matters.

## Output

Keep it scannable. No paragraph longer than three lines.

1. **Verdict:** one line on how it went.
2. **What went wrong:** a table, most costly first.

   | Issue | Evidence | Cost | Fix going forward |
   |---|---|---|---|

   Evidence is a quote or a file reference, not a paraphrase. Cost is what it cost the user (time, a wrong fact sent out, lost work). If nothing meaningful went wrong, write that in one line and skip the table.
3. **What went well:** a table, up to four rows.
4. **Through the reader's eyes** (only when a work product is in scope and something in it would change the outcome for that reader): up to five bullets, strongest concern first. Quote the exact line and give a suggested rewrite. Rewrites keep the user's facts exactly as the user gave them.
5. **New rules:** each lesson as one imperative line, specific enough that a future session could follow it without this conversation. Leave out one-off trivia and anything already recorded. If nothing durable came out of the session, say "No new rules" and do not invent one.

## After the critique

- **Saving the rules.** If the user's standing instructions already say where lessons go, save them there and say what you wrote. If not, ask once whether to save them and where. Sharpen an existing rule rather than adding a near-duplicate.
- **Acting on the fixes.** Do not start fixing things. A critique is a report; the user decides which findings are worth acting on. Close with one short question offering to apply the fixes (all, some or none).

## Tone

Name each of your mistakes plainly, once, then move to the fix. No apology spirals, and no softening a real problem to be kind. When the critique is done, the session carries on: never suggest wrapping up, taking a break or coming back later. The user decides when to stop.
