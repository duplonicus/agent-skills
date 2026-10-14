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

*(Task 1 was done one per turn in the same format. The user ran each command, the assistant checked the output in a line or two and ticked the task in the guide.)*

**Assistant:** **Linux 2/5 — watch the log live**
Goal: get mailsort's log scrolling live in your terminal, then send yourself a test mail and watch it get filed.
Before you run it: which line shows the mail being filed, and into which folder?

**User:** hint

**Assistant:** This is a `journalctl` job.

**User:** another hint

**Assistant:** It has a flag that keeps following new lines as they arrive, and one that picks the unit. It is a user service, so it needs the same switch you used in task 1.

