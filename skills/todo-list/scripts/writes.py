#!/usr/bin/env python3
"""Build the ArtifactData `batch` writes for one change to a To-Do List artifact.

The page expects every change to come with a matching `history` doc, and every
delete to carry a snapshot so its Restore button works. Getting those details
right by hand is where mistakes creep in, so this script produces the exact
`writes` array; paste its output into an ArtifactData call with action "batch".

Usage (prints JSON to stdout):
  writes.py add       --list SLUG --list-name NAME --text "Milk" [--text "Eggs" ...]
  writes.py check     --list-name NAME --item ITEM_JSON
  writes.py uncheck   --list-name NAME --item ITEM_JSON
  writes.py edit      --list-name NAME --item ITEM_JSON --new-text "Oat milk"
  writes.py move      --list TARGET_SLUG --list-name TARGET_NAME --item ITEM_JSON [--item ...]
  writes.py delete    --list-name NAME --item ITEM_JSON [--item ITEM_JSON ...]
  writes.py new-list  --name "Hardware store" [--existing-slugs a,b] [--order N]
  writes.py rename    --list SLUG --old-name OLD --name NEW --version V
  writes.py delete-list --list LIST_JSON [--item ITEM_JSON ...]

ITEM_JSON / LIST_JSON is one document exactly as ArtifactData returned it:
{"id": "...", "data": {...}, "version": N}. The version pins the write so a
change someone made on the page in the meantime is never overwritten.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone


def now():
    ms = int(time.time() * 1000)
    iso = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"
    return ms, iso


def history(ms, iso, kind, text, list_slug, list_name, snapshot=None, n=0):
    data = {"at": iso, "type": kind, "text": text, "list": list_slug,
            "listName": list_name, "by": "claude", "restored": False}
    if snapshot is not None:
        data["snapshot"] = snapshot
    return {"op": "set", "collection": "history", "doc_id": f"h{ms}{n:02d}", "data": data}


def load(doc_json):
    doc = json.loads(doc_json)
    if not isinstance(doc, dict) or not isinstance(doc.get("data"), dict) or "id" not in doc \
            or not isinstance(doc.get("version"), int):
        sys.exit("Pass the document exactly as ArtifactData returned it: {\"id\", \"data\", \"version\"}.")
    return doc


def need(ok, message):
    # Fail before printing anything: a half-built batch would leave the page inconsistent.
    if not ok:
        sys.exit(message)


def flat(doc):
    # Snapshots store {id, ...fields} so the page can recreate the doc under its original id.
    return {"id": doc["id"], **doc["data"]}


def slugify(name):
    return (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "list")[:40]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["add", "check", "uncheck", "edit", "move", "delete", "new-list", "rename", "delete-list"])
    p.add_argument("--list")
    p.add_argument("--list-name")
    p.add_argument("--name")
    p.add_argument("--old-name")
    p.add_argument("--text", action="append")
    p.add_argument("--new-text")
    p.add_argument("--item", action="append", default=[])
    p.add_argument("--existing-slugs", default="")
    p.add_argument("--order", type=float)
    p.add_argument("--version", type=int)
    a = p.parse_args()
    ms, iso = now()
    w = []

    if a.action == "add":
        if not (a.list and a.list_name and a.text):
            sys.exit("add needs --list, --list-name and at least one --text")
        for n, t in enumerate(a.text):
            # order = epoch ms, like the page's Date.now(): new items land at the bottom of the open list.
            w.append({"op": "set", "collection": "items", "doc_id": f"c{ms}{n:02d}",
                      "data": {"list": a.list, "text": t, "done": False, "created": iso,
                               "doneAt": None, "order": ms + n}})
            w.append(history(ms, iso, "add", f"Added “{t}”", a.list, a.list_name, n=n))

    elif a.action in ("check", "uncheck"):
        need(a.list_name and a.item, f"{a.action} needs --list-name and at least one --item")
        for n, raw in enumerate(a.item):
            it = load(raw)
            done = a.action == "check"
            w.append({"op": "update", "collection": "items", "doc_id": it["id"], "if_version": it["version"],
                      "data": {"done": done, "doneAt": iso if done else None}})
            verb = "Checked off" if done else "Unchecked"
            w.append(history(ms, iso, a.action, f"{verb} “{it['data']['text']}”",
                             it["data"]["list"], a.list_name, n=n))

    elif a.action == "edit":
        need(a.list_name and len(a.item) == 1 and a.new_text, "edit needs --list-name, one --item and --new-text")
        it = load(a.item[0])
        w.append({"op": "update", "collection": "items", "doc_id": it["id"], "if_version": it["version"],
                  "data": {"text": a.new_text}})
        w.append(history(ms, iso, "edit", f"Changed “{it['data']['text']}” to “{a.new_text}”",
                         it["data"]["list"], a.list_name))

    elif a.action == "move":
        if not (a.list and a.list_name and a.item):
            sys.exit("move needs --list (target slug), --list-name (target name) and --item")
        for n, raw in enumerate(a.item):
            it = load(raw)
            w.append({"op": "update", "collection": "items", "doc_id": it["id"], "if_version": it["version"],
                      "data": {"list": a.list, "order": ms + n}})
            w.append(history(ms, iso, "edit", f"Moved “{it['data']['text']}” to {a.list_name}",
                             a.list, a.list_name, n=n))

    elif a.action == "delete":
        need(a.list_name and a.item, "delete needs --list-name and at least one --item")
        items = [load(r) for r in a.item]
        for it in items:
            w.append({"op": "delete", "collection": "items", "doc_id": it["id"], "if_version": it["version"]})
        # One history entry per delete, each with its own snapshot, so each can be restored on its own.
        for n, it in enumerate(items):
            w.append(history(ms, iso, "delete-item", f"Deleted “{it['data']['text']}”",
                             it["data"]["list"], a.list_name, snapshot={"items": [flat(it)]}, n=n))

    elif a.action == "new-list":
        need(a.name, "new-list needs --name")
        taken = set(filter(None, a.existing_slugs.split(",")))
        slug = slugify(a.name)
        if slug in taken or slug == "__history":
            slug = f"{slug}-{ms:x}"
        order = a.order if a.order is not None else 1000
        w.append({"op": "set", "collection": "lists", "doc_id": slug, "data": {"name": a.name, "order": order}})
        w.append(history(ms, iso, "new-list", f"Made list “{a.name}”", slug, a.name))

    elif a.action == "rename":
        need(a.list and a.old_name and a.name and a.version is not None,
             "rename needs --list, --old-name, --name and --version (the list doc's version, so the write is pinned)")
        w.append({"op": "update", "collection": "lists", "doc_id": a.list, "if_version": a.version,
                  "data": {"name": a.name}})
        w.append(history(ms, iso, "rename-list", f"Renamed list “{a.old_name}” to “{a.name}”",
                         a.list, a.name))

    elif a.action == "delete-list":
        need(a.list, "delete-list needs --list (the list doc as ArtifactData returned it)")
        lst = load(a.list)
        items = [load(r) for r in a.item]
        for it in items:
            w.append({"op": "delete", "collection": "items", "doc_id": it["id"], "if_version": it["version"]})
        w.append({"op": "delete", "collection": "lists", "doc_id": lst["id"], "if_version": lst["version"]})
        count = f" ({len(items)} item{'s' if len(items) != 1 else ''})" if items else ""
        w.append(history(ms, iso, "delete-list", f"Deleted list “{lst['data']['name']}”{count}",
                         lst["id"], lst["data"]["name"],
                         snapshot={"list": flat(lst), "items": [flat(i) for i in items]}))

    if len(w) > 50:
        sys.exit(f"{len(w)} writes: over the 50-per-batch limit. Split the change into smaller batches.")
    print(json.dumps(w, ensure_ascii=False))


if __name__ == "__main__":
    main()
