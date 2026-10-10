"""Contract tests for skills/todo-list/scripts/writes.py.

The page only stays consistent if every change arrives with its history entry,
every delete carries a snapshot the Restore button can use, and every write to
an existing document is pinned to the version that was read.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "todo-list" / "scripts" / "writes.py"
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
ITEM_FIELDS = {"list", "text", "done", "created", "doneAt", "order"}
HISTORY_FIELDS = {"at", "type", "text", "list", "listName", "by", "restored"}


def run(*args):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
    return proc


def writes(*args):
    proc = run(*args)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def item(doc_id="i1", text="Eggs", lst="shopping", done=False, version=3):
    return json.dumps({"id": doc_id, "version": version, "data": {
        "list": lst, "text": text, "done": done, "created": "2026-01-01T00:00:00.000Z",
        "doneAt": "2026-01-02T00:00:00.000Z" if done else None, "order": 1}})


def split(ws):
    return ([w for w in ws if w["collection"] != "history"],
            [w for w in ws if w["collection"] == "history"])


def assert_batch_shape(ws):
    """Invariants every batch must hold, whatever the action."""
    assert 1 <= len(ws) <= 50
    ids = [(w["collection"], w["doc_id"]) for w in ws]
    assert len(set(ids)) == len(ids), "a batch may address each document only once"
    for w in ws:
        assert w["op"] in {"set", "update", "delete"}
        assert re.fullmatch(r"[A-Za-z0-9_\-.~:@+]{1,200}", w["doc_id"])
        if w["op"] in {"update", "delete"}:
            assert isinstance(w.get("if_version"), int), f"unpinned write: {w}"
    _, hist = split(ws)
    for h in hist:
        assert h["op"] == "set"
        assert HISTORY_FIELDS <= set(h["data"])
        assert h["data"]["by"] == "claude" and h["data"]["restored"] is False
        assert ISO.match(h["data"]["at"])
        assert h["data"]["listName"], "history needs the list name to read right after a rename"


def test_add_writes_one_item_and_one_history_entry_per_text():
    ws = writes("add", "--list", "costco", "--list-name", "Costco", "--text", "Paper towels", "--text", "Coffee")
    assert_batch_shape(ws)
    docs, hist = split(ws)
    assert [d["data"]["text"] for d in docs] == ["Paper towels", "Coffee"]
    for d in docs:
        assert d["op"] == "set" and d["collection"] == "items" and "if_version" not in d
        assert set(d["data"]) == ITEM_FIELDS
        assert d["data"]["list"] == "costco" and d["data"]["done"] is False and d["data"]["doneAt"] is None
        assert ISO.match(d["data"]["created"])
    assert docs[0]["data"]["order"] < docs[1]["data"]["order"]
    # The add box's suggestions parse this exact text, curly quotes included.
    assert [h["data"]["text"] for h in hist] == ["Added “Paper towels”", "Added “Coffee”"]
    assert all(h["data"]["type"] == "add" and h["data"]["list"] == "costco" for h in hist)


def test_check_pins_the_version_and_stamps_done_at():
    ws = writes("check", "--list-name", "Shopping", "--item", item(version=7))
    assert_batch_shape(ws)
    (doc,), (h,) = split(ws)
    assert doc == {"op": "update", "collection": "items", "doc_id": "i1", "if_version": 7,
                   "data": {"done": True, "doneAt": doc["data"]["doneAt"]}}
    assert ISO.match(doc["data"]["doneAt"])
    assert h["data"]["type"] == "check" and h["data"]["text"] == "Checked off “Eggs”"
    assert h["data"]["list"] == "shopping" and h["data"]["listName"] == "Shopping"


def test_uncheck_clears_done_at():
    ws = writes("uncheck", "--list-name", "Shopping", "--item", item(done=True))
    assert_batch_shape(ws)
    (doc,), (h,) = split(ws)
    assert doc["data"] == {"done": False, "doneAt": None}
    assert h["data"]["type"] == "uncheck" and h["data"]["text"] == "Unchecked “Eggs”"


def test_edit_changes_only_the_text():
    ws = writes("edit", "--list-name", "Shopping", "--item", item(text="Milk"), "--new-text", "Oat milk")
    assert_batch_shape(ws)
    (doc,), (h,) = split(ws)
    assert doc["data"] == {"text": "Oat milk"} and doc["if_version"] == 3
    assert h["data"]["text"] == "Changed “Milk” to “Oat milk”"


def test_move_retargets_the_item_and_logs_against_the_target_list():
    ws = writes("move", "--list", "costco", "--list-name", "Costco", "--item", item(), "--item", item("i2", "Milk"))
    assert_batch_shape(ws)
    docs, hist = split(ws)
    assert [d["doc_id"] for d in docs] == ["i1", "i2"]
    assert all(d["op"] == "update" and d["data"]["list"] == "costco" for d in docs)
    assert all(set(d["data"]) == {"list", "order"} for d in docs)
    assert [h["data"]["text"] for h in hist] == ["Moved “Eggs” to Costco", "Moved “Milk” to Costco"]
    assert all(h["data"]["list"] == "costco" for h in hist)


def test_delete_carries_a_restorable_snapshot_per_item():
    ws = writes("delete", "--list-name", "Shopping", "--item", item(), "--item", item("i2", "Milk", done=True))
    assert_batch_shape(ws)
    docs, hist = split(ws)
    assert [(d["op"], d["doc_id"], d["if_version"]) for d in docs] == [("delete", "i1", 3), ("delete", "i2", 3)]
    assert len(hist) == 2
    for h, original in zip(hist, (json.loads(item()), json.loads(item("i2", "Milk", done=True)))):
        assert h["data"]["type"] == "delete-item"
        # Restore recreates the document under its original id with every field it had.
        assert h["data"]["snapshot"] == {"items": [{"id": original["id"], **original["data"]}]}


def test_new_list_slugs_the_name_and_avoids_taken_slugs():
    (doc, h) = writes("new-list", "--name", "Hardware store", "--existing-slugs", "costco,todo", "--order", "3000")
    assert doc == {"op": "set", "collection": "lists", "doc_id": "hardware-store",
                   "data": {"name": "Hardware store", "order": 3000}}
    assert h["data"]["type"] == "new-list" and h["data"]["list"] == "hardware-store"
    taken = writes("new-list", "--name", "Costco", "--existing-slugs", "costco,todo")[0]
    assert taken["doc_id"] != "costco" and taken["doc_id"].startswith("costco-")
    assert taken["data"]["name"] == "Costco"


def test_rename_is_pinned():
    ws = writes("rename", "--list", "costco", "--old-name", "Costco", "--name", "Costco run", "--version", "4")
    assert_batch_shape(ws)
    (doc,), (h,) = split(ws)
    assert doc == {"op": "update", "collection": "lists", "doc_id": "costco", "if_version": 4,
                   "data": {"name": "Costco run"}}
    assert h["data"]["text"] == "Renamed list “Costco” to “Costco run”" and h["data"]["listName"] == "Costco run"


def test_delete_list_removes_its_items_and_snapshots_everything():
    lst = json.dumps({"id": "shopping", "version": 2, "data": {"name": "Shopping", "order": 1000}})
    ws = writes("delete-list", "--list", lst, "--item", item(), "--item", item("i2", "Milk"))
    assert_batch_shape(ws)
    docs, (h,) = split(ws)
    assert [(d["collection"], d["doc_id"]) for d in docs] == [("items", "i1"), ("items", "i2"), ("lists", "shopping")]
    assert all(d["op"] == "delete" for d in docs)
    snap = h["data"]["snapshot"]
    assert snap["list"] == {"id": "shopping", "name": "Shopping", "order": 1000}
    assert [i["id"] for i in snap["items"]] == ["i1", "i2"]
    assert h["data"]["text"] == "Deleted list “Shopping” (2 items)"


def test_more_than_50_writes_is_refused_not_truncated():
    proc = run("add", "--list", "x", "--list-name", "X", *sum((["--text", f"t{i}"] for i in range(26)), []))
    assert proc.returncode != 0 and proc.stdout == "" and "50" in proc.stderr


@pytest.mark.parametrize("args", [
    ["add", "--list", "x", "--list-name", "X"],                      # nothing to add
    ["check", "--list-name", "Shopping"],                            # no item
    ["check", "--item", item()],                                     # history would have no list name
    ["edit", "--list-name", "Shopping", "--item", item()],           # would set the text to null
    ["edit", "--list-name", "Shopping", "--new-text", "Oat milk"],   # no item
    ["delete", "--list-name", "Shopping"],                           # no item
    ["move", "--list", "costco", "--item", item()],                  # no target name
    ["new-list"],                                                    # no name
    ["rename", "--list", "costco", "--old-name", "Costco", "--name", "New"],  # unpinned write
    ["delete-list"],                                                 # no list
    ["check", "--list-name", "Shopping", "--item", '{"text": "Eggs"}'],        # not a full document
    ["check", "--list-name", "Shopping", "--item", '{"id": "i1", "data": {"text": "Eggs", "list": "s"}}'],  # no version
])
def test_incomplete_input_fails_cleanly_and_prints_no_writes(args):
    proc = run(*args)
    assert proc.returncode != 0, proc.stdout
    assert proc.stdout == "", "a partial batch must never reach stdout"
    assert "Traceback" not in proc.stderr


# ---------- due dates and calendar reminders ----------

def due_item(due="2026-10-16T15:00", event="ev1", cal_due="same", **kw):
    doc = json.loads(item(**kw))
    doc["data"]["due"] = due
    if event:
        doc["data"].update(calEvent=event, calDue=due if cal_due == "same" else cal_due)
    return json.dumps(doc)


def test_add_with_a_due_date_and_its_calendar_event():
    ws = writes("add", "--list", "todo", "--list-name", "Todo", "--text", "Call dentist",
                "--due", "2026-10-16T15:00", "--event-id", "ev9")
    assert_batch_shape(ws)
    (doc,), (h,) = split(ws)
    assert set(doc["data"]) == ITEM_FIELDS | {"due", "calEvent", "calDue"}
    assert doc["data"]["due"] == doc["data"]["calDue"] == "2026-10-16T15:00"
    assert doc["data"]["calEvent"] == "ev9"
    # Still the exact text the add box's suggestions parse.
    assert h["data"]["text"] == "Added “Call dentist”"


def test_add_with_a_due_date_but_no_event_claims_no_reminder():
    (doc,), _ = split(writes("add", "--list", "todo", "--list-name", "Todo", "--text", "A", "--due", "2026-10-16"))
    assert set(doc["data"]) == ITEM_FIELDS | {"due"} and doc["data"]["due"] == "2026-10-16"


def test_due_sets_the_date_pinned_with_a_readable_history_line():
    ws = writes("due", "--list-name", "Todo", "--item", item(version=4), "--due", "2026-10-16T15:00", "--event-id", "ev1")
    assert_batch_shape(ws)
    (doc,), (h,) = split(ws)
    assert doc["op"] == "update" and doc["if_version"] == 4
    assert doc["data"] == {"due": "2026-10-16T15:00", "calEvent": "ev1", "calDue": "2026-10-16T15:00"}
    assert h["data"]["type"] == "edit" and h["data"]["text"] == "Set “Eggs” due Fri, Oct 16, 3:00 PM"


def test_due_without_an_event_leaves_the_old_link_for_the_planner_to_see():
    (doc,), (h,) = split(writes("due", "--list-name", "Todo", "--item", due_item(), "--due", "2026-10-20"))
    # calEvent and calDue are untouched, so calDue no longer equals due: reminders.py reads that as "update".
    assert doc["data"] == {"due": "2026-10-20"}
    assert h["data"]["text"] == "Set “Eggs” due Tue, Oct 20"


def test_clearing_a_due_date_unlinks_the_event_and_names_it_for_deletion():
    proc = run("due", "--list-name", "Todo", "--item", due_item(event="ev7"), "--clear")
    assert proc.returncode == 0
    (doc,), (h,) = split(json.loads(proc.stdout))
    assert doc["data"] == {"due": None, "calEvent": None, "calDue": None}
    assert h["data"]["text"] == "Removed the due date from “Eggs”"
    assert "ev7" in proc.stderr


def test_checking_off_an_item_with_a_reminder_unlinks_the_event_and_names_it():
    proc = run("check", "--list-name", "Todo", "--item", due_item(event="ev7"))
    (doc,), _ = split(json.loads(proc.stdout))
    assert doc["data"]["done"] is True and doc["data"]["calEvent"] is None and doc["data"]["calDue"] is None
    assert "due" not in doc["data"], "the date itself stays on the item"
    assert "ev7" in proc.stderr


def test_checking_off_an_item_without_a_reminder_is_unchanged():
    proc = run("check", "--list-name", "Todo", "--item", item())
    (doc,), _ = split(json.loads(proc.stdout))
    assert set(doc["data"]) == {"done", "doneAt"} and proc.stderr == ""


def test_delete_snapshot_keeps_the_due_date_but_not_the_dead_event_link():
    proc = run("delete", "--list-name", "Todo", "--item", due_item(event="ev7"))
    _, (h,) = split(json.loads(proc.stdout))
    (snap,) = h["data"]["snapshot"]["items"]
    assert snap["due"] == "2026-10-16T15:00"
    assert "calEvent" not in snap and "calDue" not in snap, "a restored item must not claim a reminder that was deleted"
    assert "ev7" in proc.stderr


def test_delete_list_snapshot_drops_event_links_too():
    lst = json.dumps({"id": "todo", "version": 2, "data": {"name": "Todo", "order": 1000}})
    proc = run("delete-list", "--list", lst, "--item", due_item(event="ev7"), "--item", item(doc_id="i2"))
    _, (h,) = split(json.loads(proc.stdout))
    assert [set(s) & {"calEvent", "calDue"} for s in h["data"]["snapshot"]["items"]] == [set(), set()]
    assert "ev7" in proc.stderr


def test_editing_the_text_of_an_item_with_a_reminder_marks_the_event_stale():
    (doc,), _ = split(writes("edit", "--list-name", "Todo", "--item", due_item(), "--new-text", "Call the dentist"))
    assert doc["data"] == {"text": "Call the dentist", "calDue": None}
    (plain,), _ = split(writes("edit", "--list-name", "Todo", "--item", item(), "--new-text", "Oat milk"))
    assert plain["data"] == {"text": "Oat milk"}


def test_synced_records_events_without_a_history_entry():
    ws = writes("synced", "--item", due_item(event=None, doc_id="a", version=2), "--event-id", "evA",
                "--item", due_item(due="2026-10-20", event=None, doc_id="b", version=5), "--event-id", "evB")
    docs, hist = split(ws)
    assert hist == []
    assert [(d["doc_id"], d["if_version"], d["data"]) for d in docs] == [
        ("a", 2, {"calEvent": "evA", "calDue": "2026-10-16T15:00"}),
        ("b", 5, {"calEvent": "evB", "calDue": "2026-10-20"})]


def test_synced_no_event_clears_the_link():
    (doc,), hist = split(writes("synced", "--item", due_item(), "--no-event"))
    assert doc["data"] == {"calEvent": None, "calDue": None} and hist == []


@pytest.mark.parametrize("args", [
    ["add", "--list", "x", "--list-name", "X", "--text", "A", "--due", "Friday"],            # not a date
    ["add", "--list", "x", "--list-name", "X", "--text", "A", "--due", "2026-02-30"],        # not a real date
    ["add", "--list", "x", "--list-name", "X", "--text", "A", "--due", "2026-10-16T25:00"],  # not a real time
    ["add", "--list", "x", "--list-name", "X", "--text", "A", "--due", "2026-10-16T15:00Z"],  # zones are not allowed
    ["add", "--list", "x", "--list-name", "X", "--text", "A", "--event-id", "ev"],           # event without a date
    ["add", "--list", "x", "--list-name", "X", "--text", "A", "--text", "B", "--due", "2026-10-16", "--event-id", "ev"],
    ["due", "--list-name", "X", "--item", item()],                                           # neither date nor clear
    ["due", "--list-name", "X", "--item", item(), "--due", "2026-10-16", "--clear"],         # both
    ["due", "--list-name", "X", "--item", item(), "--clear", "--event-id", "ev"],
    ["due", "--item", item(), "--due", "2026-10-16"],                                        # no list name
    ["synced", "--item", item(), "--event-id", "ev"],                                        # item has no due date
    ["synced", "--item", due_item()],                                                        # neither event nor no-event
    ["synced", "--item", due_item(), "--item", due_item(doc_id="i2"), "--event-id", "ev"],   # one id for two items
])
def test_bad_due_input_fails_cleanly_and_prints_no_writes(args):
    proc = run(*args)
    assert proc.returncode != 0, proc.stdout
    assert proc.stdout == "", "a partial batch must never reach stdout"
    assert "Traceback" not in proc.stderr
