# Session transcript

A terminal practice session. The user runs each command themselves with `!`; what they ran and what it printed appears below as "User ran".

---

**User:** i have an interview for a support engineer job on friday. help me practise linux and git? my study guide is project/study-guide.md

**Assistant:** Read your guide. Nine tasks, Linux then Git, then the guide's ten quiz questions from memory and a rating for the form.

How this works:
- You type every command yourself with `!`, so I can see the output. Send `done` or a question after each one.
- I give the goal, not the command. Ask for a `hint` when you are stuck.
- `hint` · `show me` · `why` · `skip` · `where are we` · `quiz me`

Two safety lines:
- `mailsort` is your real service, so it is read-only: status, logs and process listings. Never stop, restart, kill or edit it.
- Anything that changes files or history happens in `~/drill` and nowhere else.

**Linux 1/5 — is mailsort running?**
Goal: find the exact name of the mailsort unit among your user services, then get its status.
Before you run it: pick out three things: is it active, since when, and the main PID.

*(Tasks 1 to 9 were done one per turn in the same format. The user ran each command, the assistant checked the output in a line or two and ticked the task in the guide.)*

**Assistant:** That is the plan done. Where we are:

Linux
- ✓ 1 mailsort status: unaided
- ✓ 2 live log: one hint (which tool)
- ✓ 3 biggest folder: unaided
- ✓ 4 process ID: unaided
- ✓ 5 permissions: unaided

Git
- ✓ 6 three commits: unaided
- ✓ 7 move a commit to a branch: shown the command
- ✓ 8 merge conflict: two hints
- ✓ 9 bisect: shown the command

Quiz next: ten questions, one at a time, from memory. No scrolling back, no looking things up.

*(Questions 1 to 6 were asked one per turn and graded: 1 right; 2 right; 3 right; 4 right; 5 right; 6 right.)*

**Assistant:** **Question 7/10**
You know a good commit and a bad one. How do you find the commit that introduced the bug?

