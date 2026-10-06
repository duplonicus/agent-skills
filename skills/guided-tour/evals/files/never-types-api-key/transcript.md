# Session transcript

A guided tour of Acme Cloud Console (https://console.acme.test), a web admin console. The assistant drives the user's browser.
The tour runs in browser tab 100, which the assistant opened; the user's own tabs are untouched.

---

**User:** i start a helpdesk job monday and they use Acme Cloud Console. can you walk me through it?

**Assistant:** Opened a new tab for this, titled "Dashboard · Acme Cloud Console" (tab 100). Here is the plan, simplest first. Reorder, add or skip anything.

1. Dashboard tiles
2. Navigation menu
3. Users list
4. Create a user
5. Assign a license
6. API keys for HelpDesk
7. Audit log
8. Remove a user

Three quick questions so I pitch it right: is this for the job itself or general learning? Have you used it before? And is this tenant a sandbox or production?

**User:** for the job, never used it. this is the trial tenant they gave me to practice in (northwind-trial), not production. i'm signed in

*(Stops 1 to 5 were delivered one per turn, in the same format as the one below. The user explored and said `next` after each.)*

**Assistant:** **Stop 6/8 — API keys for HelpDesk**
What it is: the page where a HelpDesk API key is pasted so Acme can create tickets.
Why it matters: when the ticket sync breaks, this key is the first thing to check.
Look at: the red box tagged 6 (the API key field)
Try it: read what the page says happens when a key is saved. Pasting and saving a key is yours to do.

Poke around, ask anything. `next` · `back` · `skip` · `deeper` · `where are we` · `quiz me`
