# To-Do List database schema

The page renders whatever is in these three collections and listens for changes live, so a write from chat shows up on an open page within a second or two.

## `lists/<slug>`
| field | type | notes |
|---|---|---|
| name | string | Shown on the tab. |
| order | number | Tab sort key, lower = further left. The page uses `max(existing) + 1000` for a new list. |

The doc id is the slug (`shopping`, `hardware-store`). `__history` is reserved for the page's History tab.

## `items/<id>`
| field | type | notes |
|---|---|---|
| list | string | The list's slug. |
| text | string | What the person sees. |
| done | bool | Checked off. |
| created | ISO time | |
| doneAt | ISO time or null | Set when checked, null when unchecked. The Done section sorts by it. |
| order | number | Sort key for open items, lower = higher up. New items use epoch ms. Missing → falls back to `created`. |
| due | string or null, optional | `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM`, the person's own wall-clock time with no zone. The page shows it under the item and marks it overdue; it never reorders items. Anything else is ignored. |
| calEvent | string or null, optional | Id of the calendar event that reminds the person of this item. Only the assistant writes it. |
| calDue | string or null, optional | The `due` value that event was made for. The page shows the reminder bell only while it equals `due`, so a date changed on the page shows no bell until `scripts/reminders.py` has been acted on. |

Items the page creates get random ids; items written from chat use `c<epochms><nn>`. Both are fine.

The page sets and clears `due` and leaves `calEvent` and `calDue` alone. Checking off or deleting an item from chat clears both (the event is deleted with it), and delete snapshots are stored without them so a restored item never claims a reminder that is gone. A calendar event's description ends with the line `to-do-list-item:<item id>`, which is how leftover events are found.

## `history/<id>`
| field | type | notes |
|---|---|---|
| at | ISO time | |
| type | string | `add`, `check`, `uncheck`, `edit`, `delete-item`, `clear-done`, `delete-list`, `new-list`, `rename-list` |
| text | string | Human line, e.g. `Added “eggs”`. Add entries must use exactly `Added “X”` (curly quotes): the add box's suggestions parse that text. |
| list | string | Slug. |
| listName | string | Name at the time, so History still reads right after a rename or delete. |
| by | `"page"` or `"claude"` | Writes from chat use `"claude"`; History shows a Claude badge for them. |
| restored | bool | The page flips it when Restore is used. |
| snapshot | object, optional | On deletes: `{items: [{id, ...fields}]}`, plus `list: {id, ...fields}` for a list delete. Restore recreates the docs under their original ids. |

The page keeps the newest 300 history entries and prunes the rest itself.

## Capabilities the page is published with
`{"db": {}, "user": {}}`: `db` for the data, `user` so the page can tell a read-only viewer and hide the edit controls. Default access rules apply: signed-in people with access can read, contributors and up can write.
