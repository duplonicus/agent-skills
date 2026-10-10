"""Contract tests for skills/todo-list/scripts/reminders.py.

The calendar is the only thing that can remind anyone, so the plan has to be
exact: one event per open item with a due date that is still ahead, and no
event for anything checked off, undated or gone.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "todo-list" / "scripts" / "reminders.py"
NOW = "2026-10-10T14:00"
REMINDERS = [{"method": "popup", "minutes": 1440}, {"method": "popup", "minutes": 60}]


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def item(doc_id="i1", text="Call dentist", due=None, done=False, event=None, cal_due="same"):
    data = {"list": "todo", "text": text, "done": done, "created": "2026-10-01T00:00:00.000Z",
            "doneAt": None, "order": 1}
    if due is not None:
        data["due"] = due
    if event:
        data.update(calEvent=event, calDue=due if cal_due == "same" else cal_due)
    return json.dumps({"id": doc_id, "version": 3, "data": data})


def plan(*items, extra=()):
    proc = run("plan", "--now", NOW, *sum((["--item", i] for i in items), []), *extra)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_a_timed_item_gets_an_event_at_its_time_with_both_reminders():
    (op,) = plan(item(due="2026-10-16T15:00"))
    assert op == {"op": "create", "item": "i1", "text": "Call dentist", "event": {
        "summary": "Due: Call dentist",
        "startTime": "2026-10-16T15:00:00", "endTime": "2026-10-16T15:30:00",
        "description": "From your to-do list. Change the due date on the list, not here.\nto-do-list-item:i1",
        "overrideReminders": REMINDERS}}


def test_a_date_only_item_is_treated_as_due_at_nine_in_the_morning():
    (op,) = plan(item(due="2026-10-16"))
    assert (op["event"]["startTime"], op["event"]["endTime"]) == ("2026-10-16T09:00:00", "2026-10-16T09:30:00")
    assert op["event"]["overrideReminders"] == REMINDERS


def test_event_times_carry_no_zone_so_the_calendar_uses_the_persons_own():
    (op,) = plan(item(due="2026-10-16T15:00"))
    for key in ("startTime", "endTime"):
        assert not op["event"][key].endswith("Z") and "+" not in op["event"][key]


def test_an_item_in_step_with_its_event_needs_nothing():
    assert plan(item(due="2026-10-16T15:00", event="ev1")) == []


def test_a_date_changed_on_the_page_updates_the_same_event():
    (op,) = plan(item(due="2026-10-20T10:00", event="ev1", cal_due="2026-10-16T15:00"))
    assert op["op"] == "update" and op["eventId"] == "ev1"
    assert op["event"]["startTime"] == "2026-10-20T10:00:00"


def test_text_changed_from_chat_updates_the_event_title():
    (op,) = plan(item(text="Call the dentist", due="2026-10-16T15:00", event="ev1", cal_due=None))
    assert op["op"] == "update" and op["event"]["summary"] == "Due: Call the dentist"


@pytest.mark.parametrize("stale", [
    item(due="2026-10-16T15:00", done=True, event="ev1"),   # checked off on the page
    item(due=None, event="ev1", cal_due="2026-10-16"),      # due date removed on the page
    item(due="not a date", event="ev1"),                    # value the page would not show
])
def test_an_event_nobody_needs_any_more_is_deleted(stale):
    assert plan(stale) == [{"op": "delete", "item": "i1", "text": "Call dentist", "eventId": "ev1"}]


@pytest.mark.parametrize("quiet", [
    item(),                                    # no due date
    item(due="2026-10-16", done=True),         # done, never had an event
    item(due="2026-10-10T13:59"),              # already past
    item(due="2026-10-10"),                    # date only, 9:00 today has passed
    item(due="2026-02-30"),                    # not a real date
    item(due="2026-10-16T15:00Z"),             # zones are not part of the format
])
def test_items_that_cannot_be_reminded_of_get_no_event(quiet):
    assert plan(quiet) == []


def test_the_boundary_a_minute_ahead_still_gets_an_event():
    (op,) = plan(item(due="2026-10-10T14:01"))
    assert op["op"] == "create"


def test_each_item_gets_its_own_decision_in_order():
    ops = plan(item("a", due="2026-10-16"), item("b"), item("c", due="2026-10-17", done=True, event="evC"),
               item("d", due="2026-10-18", event="evD"))
    assert [(o["op"], o["item"]) for o in ops] == [("create", "a"), ("delete", "c")]


def test_leftover_events_of_deleted_items_are_found_from_the_calendar():
    ops = plan(item("a", due="2026-10-16", event="evA"), item("b", due="2026-10-17", event="evB2"),
               extra=["--all-items", "--event", "evA=a", "--event", "evGone=zz", "--event", "evB1=b"])
    # evA is live. evGone's item no longer exists. evB1 belongs to an item that now points at evB2.
    assert ops == [{"op": "delete", "item": "zz", "text": "", "eventId": "evGone"},
                   {"op": "delete", "item": "b", "text": "", "eventId": "evB1"}]


def test_an_event_is_never_deleted_twice():
    ops = plan(item("a", due="2026-10-16", done=True, event="evA"), extra=["--all-items", "--event", "evA=a"])
    assert [o["eventId"] for o in ops] == ["evA"]


@pytest.mark.parametrize("args", [
    ["plan"],                                                         # nothing to plan
    ["plan", "--item", item(), "--event", "ev=i1"],                   # leftovers need the whole database
    ["plan", "--all-items", "--item", item(), "--event", "ev"],       # no item id
    ["plan", "--item", '{"text": "x"}'],                              # not a document
])
def test_bad_input_fails_cleanly_and_prints_no_plan(args):
    proc = run(*args)
    assert proc.returncode != 0 and proc.stdout == "" and "Traceback" not in proc.stderr
