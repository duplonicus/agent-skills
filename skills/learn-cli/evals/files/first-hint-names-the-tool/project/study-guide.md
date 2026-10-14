# Study guide: Linux and Git

For the support engineer interview on Friday. Their form asks me to rate myself on each.
Planning to put: Linux Fair, Git Good.

## Rating scale (the form's own)
- Poor: knows the words
- Fair: needs to look most things up
- Average: comfortable on your own machine, can troubleshoot common things with some searching
- Good: could handle most day-to-day tasks on a server someone else hands you
- Excellent: certification level, production servers, from memory

## Practice plan
The real service on this machine is `mailsort`, a user service that files my mail. I use it every day.
Anything that changes files or history goes in `~/drill` (Git in `~/drill/repo`).

Linux
- [x] 1. Find the mailsort unit and see whether it is running
- [ ] 2. Watch its log live while a test mail arrives
- [ ] 3. Find the biggest folder in my home directory
- [ ] 4. Find the mailsort process ID
- [ ] 5. In ~/drill, make a file that its owner can read and write, its group can read and nobody else can touch. Prove it.

Git
- [ ] 6. New repository with three commits
- [ ] 7. Commit to main by mistake, then move that commit to a branch
- [ ] 8. Make two branches change the same line, merge, resolve the conflict
- [ ] 9. Plant a bug in an early commit and find it with bisect

## Quiz
1. A systemd service has stopped. What are your first commands?
2. The disk is full. How do you find what is eating the space?
3. A process is hung. How do you find it and stop it, and what is the difference between kill and kill -9?
4. What does chmod 640 do?
5. How do you watch a service's log live while you reproduce a bug?
6. What are strace and lsof for?
7. You know a good commit and a bad one. How do you find the commit that introduced the bug?
8. You committed to main by mistake and have not pushed. How do you move the commit to a new branch?
9. Merge or rebase: what is the difference?
10. How do you resolve a merge conflict?

## Answers
1. systemctl status <unit>, then journalctl -u <unit> -n 50. Restart only once you know why. A user service needs --user on both (systemctl --user status mailsort).
2. df -h for which disk, then du -sh /var/* | sort -h (or du -sh ~/* | sort -h) for which folder.
3. ps aux | grep <name> or pgrep <name> for the PID. kill <pid> sends SIGTERM: polite, the program can clean up. kill -9 sends SIGKILL: instant, no cleanup. Try plain kill first.
4. Owner can read and write, group can read, everyone else nothing (r=4, w=2, x=1). Check with ls -l: -rw-r-----.
5. journalctl -u <unit> -f (journalctl --user -u mailsort -f for a user service), or tail -f on a log file.
6. strace shows the system calls a program makes, so where it hangs. lsof shows open files and ports.
7. git bisect start, git bisect bad, git bisect good <ref>, test each step and mark it, git bisect reset at the end.
8. git branch fix, git reset --hard HEAD~1, git switch fix. The reset drops uncommitted work, so commit or stash first.
9. Merge joins two branches with a merge commit and keeps the true history. Rebase replays your commits on top for a straight line. Never rebase commits other people have pulled.
10. git status, edit the files between the <<<<<<< ======= >>>>>>> markers, remove the markers, git add, git commit. git merge --abort backs out.
