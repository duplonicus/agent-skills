---
name: todo-list
description: Keeps the person's lists (shopping, groceries, todo, any store or errand list) in a To-Do List artifact backed by a live database, and sets that artifact up if they don't have one yet. Use it whenever someone asks to add, check off, cross out, remove, move or rename something on a list, asks what's on a list, says "show me my list", "put X on my Costco list", "I'm out of milk", "make a list for the hardware store", or wants a list or checklist they can edit by hand and through chat, even if they never say "artifact".
license: MIT
compatibility: Needs Claude's Artifact and ArtifactData tools (a published artifact page with a shared database), and Python 3 to run the helper script.
metadata:
  author: duplonicus
  version: "1.0"
---

# To-Do List

The person's lists live in one published artifact page. The page reads a small database (`lists`, `items`, `history`) and redraws live, so you change the lists by writing that database with the **ArtifactData** tool, never by republishing the page. Republishing would replace their page for no gain and can clobber edits made on it.

Load `ArtifactData` (and `Artifact` if it is deferred) with ToolSearch before the first call.

## 1. Find their list artifact

Look in this order and stop at the first hit:

1. **Their notes.** If a memory tool or saved preferences mention a To-Do List / lists artifact URL, use it.
2. **Their artifacts.** `Artifact` with `action: "list"` (scope `mine`, limit 50). Look for a title like "To-Do List", "Lists", "Shopping list". If several fit, ask which one.
3. **Nothing found** → go to section 5 (set one up).

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

Also: `uncheck`, `edit --new-text`, `rename --list <slug> --old-name --name --version`, `delete-list --list '<list doc>' --item ...` (pass every item on that list so the snapshot can restore them). `--item` takes the full document `{"id","data","version"}` from your read. That version is what stops you overwriting a change someone just made on the page.

Why the history entry matters: History is the page's undo. Add entries also feed the add box's autocomplete, and a delete without a snapshot can't be restored. Writing items without their history entry leaves the page quietly inconsistent, which is why the helper always emits both.

Notes:
- Adding something already open on that list: say it's already there instead of adding a duplicate. If it's in Done, uncheck it rather than adding a new copy.
- Several changes at once go in one batch (50 writes max; the helper warns past that).
- If the batch fails on a version conflict, someone edited that doc on the page. Re-read it, rebuild the writes, try once more.
- "Move X to the Costco list": `writes.py move --list costco --list-name Costco --item '<item doc>'`.

## 4. Reply

Keep it to one line: what changed and on which list ("Added paper towels and coffee to Costco."). When they ask to **see** the list, use `Artifact` `action: "open"` with the URL instead of pasting the items. When they ask **what's on** a list, answer in chat from the items you read: open items first, then how many are done.

## 5. No list artifact yet: set one up

The page ships with this skill as `assets/todo-list.html`. If the person asked to add something and you found no list artifact, tell them in a line and offer to set one up; if they asked for a list or checklist to be made, just do it.

1. Copy `assets/todo-list.html` into your working directory (or scratchpad) as `todo-list.html`. Leave its content alone; the page expects the schema in `references/schema.md`.
2. Publish it: `Artifact` with `file_path` set to that copy, `capabilities: {"db": {}, "user": {}}`, `icon: "checklist"`, and a one-sentence `description`. `db` holds the lists; `user` lets the page hide edit controls from people who can only view.
3. Seed the lists through the database, not the HTML: run `writes.py new-list` for each list they want (default to one "Shopping" and one "Todo" if they didn't say), then add any items they mentioned. A page that hardcodes starting data would reset them on every republish.
4. Check it worked: `ArtifactData` `list` on `lists` and `items` should show what you wrote.
5. Tell them in one or two lines: the page is private until they share it, they can type into it directly or ask you, and History can restore anything deleted. Offer once to pin it to their sidebar (`Artifact` `action: "pin"`, only on a yes). Save the URL to memory if you can.

`references/schema.md` has every field, if you need to do something the helper doesn't cover.
