---
name: todo-list
description: Keeps the person's lists (shopping, groceries, todo, any store or errand list) in a To-Do List artifact backed by a live database, and sets that artifact up if they don't have one yet. Use it whenever someone asks to add, check off, cross out, remove, move or rename something on a list, asks what's on a list, says "show me my list", "put X on my Costco list", "I'm out of milk", "make a list for the hardware store", or wants a list or checklist they can edit by hand and through chat, even if they never say "artifact". Also use it for due dates and reminders on list items, like "add X due Friday at 3", "remind me about X", "when is X due", "sync my reminders".
license: MIT
compatibility: Needs Claude's Artifact and ArtifactData tools (a published artifact page with a shared database), and Python 3 to run the helper scripts. Reminders also need a calendar tool that can create events with custom reminder times; without one, due dates still show on the page.
metadata:
  author: duplonicus
  version: "1.1"
---

# To-Do List

The person's lists live in one published artifact page. The page reads a small database (`lists`, `items`, `history`) and redraws live, so you change the lists by writing that database with the **ArtifactData** tool, never by republishing the page. Republishing would replace their page for no gain and can clobber edits made on it.

Load `ArtifactData` (and `Artifact` if it is deferred) with ToolSearch before the first call.

## 1. Find their list artifact

Look in this order and stop at the first hit:

1. **Their notes.** If a memory tool or saved preferences mention a To-Do List / lists artifact URL, use it.
2. **Their artifacts.** `Artifact` with `action: "list"` (scope `mine`, limit 50). Look for a title like "To-Do List", "Lists", "Shopping list". If several fit, ask which one.
3. **Nothing found** → go to section 6 (set one up).

If you found it via step 2 and the session has a memory tool, save the URL there so next time is instant.

## 2. Read the live data before every answer or write

Notes about which lists exist go stale the moment someone adds a list on the page. So before you say a list does or doesn't exist, or write anything, read the live state:

- `ArtifactData` `list` on `lists` (gives slugs, names and order).
- `ArtifactData` `query` on `items` with `where: [["list","==","<slug>"]]` when you need that list's items (to check, delete, avoid duplicates, or answer "what's on it").

**Matching the person's words to a list.** Match on the list's `name` loosely: case, plurals, "my", "the", "list" and the store-vs-errand wording all shouldn't matter ("costco list", "Costco", "stuff from costco" → `costco`). Match items the same way ("the milk" → "2% milk"). If two lists or items fit equally well, ask.

**When the list they named doesn't exist,** decide by whether any existing list could plausibly be what they meant:
- **Nothing close** ("hardware store" when the lists are Shopping, Todo, Groceries): make the list and add the item in the same batch, and say so in the reply ("You didn't have a Hardware store list, so I made one and added sponges."). They named the list, so making it is what they asked for, and it's one tap to delete.
- **Something might be it** ("home depot" when there's a "Hardware" list, "groceries" when there's "Food shopping"): ask which they meant before writing.
- Never put the item on a different list than the one they named without asking.

## 3. Make the change with the helper

`scripts/writes.py` builds the exact `writes` array for one change: the item or list docs, the matching `history` entry the page shows, the snapshot that makes deletes restorable, and version pins. Run it, then pass its output as `writes` in one `ArtifactData` call with `action: "batch"`.

```bash
python3 <skill-dir>/scripts/writes.py add --list costco --list-name Costco --text "Paper towels" --text "Coffee"
python3 <skill-dir>/scripts/writes.py check --list-name Costco --item '<item doc as ArtifactData returned it>'
python3 <skill-dir>/scripts/writes.py delete --list-name Costco --item '<item doc>' --item '<item doc>'
python3 <skill-dir>/scripts/writes.py new-list --name "Hardware store" --existing-slugs costco,todo --order <max list order + 1000>
```

Due dates: `add ... --due 2026-10-16T15:00`, `due --list-name Todo --item '<item doc>' --due 2026-10-16` (or `--clear`). Section 4 covers the reminder that goes with one.

Also: `uncheck`, `edit --new-text`, `rename --list <slug> --old-name --name --version`, `delete-list --list '<list doc>' --item ...` (pass every item on that list so the snapshot can restore them). `--item` takes the full document `{"id","data","version"}` from your read. That version is what stops you overwriting a change someone just made on the page.

Why the history entry matters: History is the page's undo. Add entries also feed the add box's autocomplete, and a delete without a snapshot can't be restored. Writing items without their history entry leaves the page quietly inconsistent, which is why the helper always emits both.

Notes:
- Adding something already open on that list: say it's already there instead of adding a duplicate. If it's in Done, uncheck it rather than adding a new copy.
- Several changes at once go in one batch (50 writes max; the helper warns past that).
- If the batch fails on a version conflict, someone edited that doc on the page. Re-read it, rebuild the writes, try once more.
- "Move X to the Costco list": `writes.py move --list costco --list-name Costco --item '<item doc>'`.

## 4. Due dates and reminders

An item can carry a `due` field: a date (`2026-10-16`) or a date and time (`2026-10-16T15:00`). It is the person's own wall-clock time, with no time zone and no `Z`. Work out "Friday" or "tomorrow at 3" from today's date in their zone; if you can't tell which day they mean, ask. The page shows it under the item, turns it red when it is overdue, and lets them set or change it by tapping the item.

The page can't notify anyone, so **the reminder is a calendar event**: one event per open item with a due date, with a pop-up reminder one day before and one hour before. A date with no time counts as due at 9:00 that morning. The item remembers its event in `calEvent`, and in `calDue` the due date that event was made for; the page shows a bell only while `calDue` equals `due`.

**The page also does this by itself** when it was published with the calendar connector (section 6) and the person has Google Calendar connected: setting, changing or removing a date on the page, checking an item off, or deleting it creates, moves or removes the event right then, using the same rules as `reminders.py`. So after a change made on the page there is usually nothing left for you to do, and `reminders.py plan` returns `[]`. Changes made from chat are still yours to sync; the page only shows an "Update reminders" button for them.

**No calendar tool in this session?** Set the due date anyway and say in the reply that it shows on the list but no reminder was set. Never write `--event-id` for an event you did not create.

**Setting a due date from chat** (calendar tool available):
1. Run `python3 <skill-dir>/scripts/reminders.py plan --item '<item doc with the new due date>'`. For an item that doesn't exist yet, add it first without `--event-id`, re-read it, then plan. The output is the exact calendar call to make: `event` holds the title, start, end, description and reminders. Pass the times as given and do not add a time zone.
2. Make the call (create, update or delete), then record it: `writes.py synced --item '<item doc>' --event-id <id the calendar returned>`, or `--no-event` after a delete. Send that as a batch like any other change.

**Whenever you've read a list's items for any reason,** run `reminders.py plan` on them with one `--item` each. It is a local script and costs nothing. `[]` means the calendar already matches. Anything else is a change someone made on the page that the calendar hasn't caught up with (a date moved, an item checked off, a due date set by hand): make those calls and record them with `synced`. This is how a date set on the page gets its reminder.

**When `writes.py` prints "Delete these calendar events too"** (on check, delete, delete-list or `due --clear`), delete those events. The helper has already dropped the link from the item, so nothing else will remember them.

**"Sync my reminders"**, or any time you want to be thorough: read every item, search the calendar for upcoming events whose description contains `to-do-list-item:`, and run `reminders.py plan --all-items --item ... --event <event id>=<item id from that line> ...`. This also finds events left behind by items deleted on the page, which no other step can see.

Past due dates get no event. Tell the person the reminder times in the reply when you set one ("Added, due Fri 3:00 PM. Reminders set for Thu 3:00 PM and Fri 2:00 PM.").

## 5. Reply

Keep it to one line: what changed and on which list ("Added paper towels and coffee to Costco."). When they ask to **see** the list, use `Artifact` `action: "open"` with the URL instead of pasting the items. When they ask **what's on** a list, answer in chat from the items you read: open items first, then how many are done.

## 6. No list artifact yet: set one up

The page ships with this skill as `assets/todo-list.html`. If the person asked to add something and you found no list artifact, tell them in a line and offer to set one up; if they asked for a list or checklist to be made, just do it.

1. Copy `assets/todo-list.html` into your working directory (or scratchpad) as `todo-list.html`. Leave its content alone; the page expects the schema in `references/schema.md`.
2. Publish it: `Artifact` with `file_path` set to that copy, `icon: "checklist"`, a one-sentence `description`, and `capabilities`:
   - If this session has a Google Calendar connector: `{"db": {}, "user": {}, "mcp": {"servers": [{"server": "<its connector segment, e.g. claude_ai_Google_Calendar>", "tools": ["create_event", "update_event", "delete_event"]}]}}`. That lets the page make calendar reminders for due dates itself. The page calls the connector by its display name, "Google Calendar"; if the publish result names it differently, change the `CAL` constant near the top of the page's script and publish again.
   - Otherwise: `{"db": {}, "user": {}}`. Due dates still work; reminders then come only from chat.
   - `db` holds the lists; `user` lets the page hide edit controls from people who can only view. On any later republish with `capabilities`, restate all of them: a non-empty declaration drops whatever it leaves out.
3. Seed the lists through the database, not the HTML: run `writes.py new-list` for each list they want (default to one "Shopping" and one "Todo" if they didn't say), then add any items they mentioned. A page that hardcodes starting data would reset them on every republish.
4. Check it worked: `ArtifactData` `list` on `lists` and `items` should show what you wrote.
5. Tell them in one or two lines: the page is private until they share it, they can type into it directly or ask you, and History can restore anything deleted. Offer once to pin it to their sidebar (`Artifact` `action: "pin"`, only on a yes). Save the URL to memory if you can.

`references/schema.md` has every field, if you need to do something the helper doesn't cover.
