#!/usr/bin/env python3
"""Work out which calendar events the To-Do List's due dates need.

The page cannot reach a calendar, so the reminders are calendar events the
assistant keeps in step with the items: one event per open item with a due
date, with a reminder a day before and an hour before. This script compares
the items with what they say about their events and prints what to do; it
calls nothing itself.

Usage (prints a JSON array to stdout):
  reminders.py plan --item ITEM_JSON [--item ITEM_JSON ...] [--now 2026-10-10T14:00]
  reminders.py plan --all-items --item ... --event EVENT_ID=ITEM_ID [--event ...]

The second form also finds leftovers: pass EVERY item in the database, plus
one --event for each calendar event whose description holds a
"to-do-list-item:<id>" line. Events whose item is gone, or now points at a
different event, come back as deletes. An item deleted on the page leaves
its event behind, and this is the only way to find it.

ITEM_JSON is one item exactly as ArtifactData returned it:
{"id": "...", "data": {...}, "version": N}.

Each entry is one calendar call:
  {"op": "create", "item": ID, "text": ..., "event": {summary, startTime, endTime, description, overrideReminders}}
  {"op": "update", "item": ID, "text": ..., "eventId": EID, "event": {...}}
  {"op": "delete", "item": ID, "text": ..., "eventId": EID}
An empty array means the calendar already matches. After a create or update,
record it with `writes.py synced --item ... --event-id ...`; after a delete,
with `writes.py synced --item ... --no-event`.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta

DUE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$")
# A date with no time has no "hour before", so it is treated as due at 9 in the morning:
# the reminders then land at 9:00 the day before and 8:00 on the day.
DATE_ONLY_AT = "09:00"
MINUTES = 30
REMINDERS = [{"method": "popup", "minutes": 24 * 60}, {"method": "popup", "minutes": 60}]
MARK = "to-do-list-item:"


def start_of(due):
    """The moment an item is due, or None when the value is not a real date."""
    if not isinstance(due, str) or not DUE.match(due):
        return None
    try:
        return datetime.strptime(due if "T" in due else f"{due}T{DATE_ONLY_AT}", "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def event_for(item_id, data, start):
    stamp = "%Y-%m-%dT%H:%M:%S"
    return {
        "summary": f"Due: {data['text']}",
        "startTime": start.strftime(stamp),
        "endTime": (start + timedelta(minutes=MINUTES)).strftime(stamp),
        "description": "From your to-do list. Change the due date on the list, not here.\n" + MARK + item_id,
        "overrideReminders": REMINDERS,
    }


def plan(items, now, events=()):
    ops = []
    for doc in items:
        d, item_id = doc["data"], doc["id"]
        start = start_of(d.get("due"))
        event_id = d.get("calEvent")
        wanted = start is not None and not d.get("done")
        base = {"item": item_id, "text": d.get("text", "")}
        if not wanted:
            if event_id:
                ops.append({"op": "delete", **base, "eventId": event_id})
        elif not event_id:
            # A date that has already passed can no longer remind anyone.
            if start > now:
                ops.append({"op": "create", **base, "event": event_for(item_id, d, start)})
        elif d.get("calDue") != d["due"]:
            ops.append({"op": "update", **base, "eventId": event_id, "event": event_for(item_id, d, start)})
    linked = {doc["id"]: doc["data"].get("calEvent") for doc in items}
    already = {op["eventId"] for op in ops if op["op"] == "delete"}
    for event_id, item_id in events:
        if linked.get(item_id) != event_id and event_id not in already:
            ops.append({"op": "delete", "item": item_id, "text": "", "eventId": event_id})
            already.add(event_id)
    return ops


def load(raw):
    doc = json.loads(raw)
    if not isinstance(doc, dict) or not isinstance(doc.get("data"), dict) or "id" not in doc:
        sys.exit("Pass each item exactly as ArtifactData returned it: {\"id\", \"data\", \"version\"}.")
    return doc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["plan"])
    p.add_argument("--item", action="append", default=[])
    p.add_argument("--now", help="local time to plan from, for tests; default is the clock")
    p.add_argument("--event", action="append", default=[], metavar="EVENT_ID=ITEM_ID")
    p.add_argument("--all-items", action="store_true",
                   help="the --item list is every item in the database (required with --event)")
    a = p.parse_args()
    if a.event and not a.all_items:
        sys.exit("--event needs --all-items: with only some items passed, every other item's event would look like a leftover")
    if not a.item and not a.all_items:
        sys.exit("plan needs at least one --item")
    events = []
    for pair in a.event:
        event_id, sep, item_id = pair.partition("=")
        if not (sep and event_id and item_id):
            sys.exit(f"--event {pair}: expected EVENT_ID=ITEM_ID")
        events.append((event_id, item_id))
    now = datetime.strptime(a.now, "%Y-%m-%dT%H:%M") if a.now else datetime.now()
    print(json.dumps(plan([load(r) for r in a.item], now, events), ensure_ascii=False))


if __name__ == "__main__":
    main()
