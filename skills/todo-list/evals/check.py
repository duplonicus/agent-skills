#!/usr/bin/env python3
"""Deterministic grading for the todo-list evals.

Usage: check.py <eval-name> <fixture-dir> <run-dir> <skill-dir>

Compares the mock database before the run (fixture state.json) with the state
after it (run state.json), plus the agent's reply, and prints a grading.json.
Every check is about the outcome: what is in the database and what the user
was told. None of them looks at how the agent got there.
"""
import json
import re
import sys
from pathlib import Path

URL = "https://claude.ai/artifact/mock-001"
ITEM_FIELDS = {"list", "text", "done", "created", "doneAt", "order"}


class Run:
    def __init__(self, fixture, run_dir):
        self.before = json.loads((fixture / "state.json").read_text())
        self.after = json.loads((run_dir / "state.json").read_text())
        self.reply = (run_dir / "outputs" / "reply.md").read_text()
        self.calls = self.after["calls"]

    def col(self, when, name):
        return getattr(self, when)["db"].get(URL, {}).get(name, {})

    def new(self, name):
        return {k: v for k, v in self.col("after", name).items() if k not in self.col("before", name)}

    def unchanged(self, name, *ids):
        b, a = self.col("before", name), self.col("after", name)
        return all(b.get(i) == a.get(i) for i in (ids or b))

    def items_like(self, pattern, when="after", lst=None):
        return {k: v for k, v in self.col(when, "items").items()
                if re.search(pattern, str(v["data"].get("text", "")), re.I)
                and (lst is None or v["data"].get("list") == lst)}

    def history_for(self, kind, item_text):
        return [h for h in self.new("history").values()
                if h["data"].get("type") == kind and item_text in str(h["data"].get("text", ""))]

    def reply_lines(self):
        return [l for l in self.reply.splitlines() if l.strip()]

    def published(self):
        return [c for c in self.calls if c["tool"] == "Artifact" and (c["args"].get("action") or "publish") == "publish"]


def well_formed(doc):
    d = doc["data"]
    return (set(d) >= ITEM_FIELDS and d["done"] is False and d["doneAt"] is None
            and isinstance(d["order"], (int, float)) and isinstance(d["created"], str))


def add_to_existing(r):
    towels, coffee = r.items_like("paper towel", lst="costco"), r.items_like("coffee", lst="costco")
    new = r.new("items")
    yield ("Paper towels and coffee are each on the Costco list exactly once",
           len(towels) == 1 and len(coffee) == 1, f"costco matches: towels={len(towels)}, coffee={len(coffee)}")
    yield ("The two new items have every field the page expects (list, text, done, created, doneAt, order)",
           len(new) == 2 and all(well_formed(d) for d in new.values()),
           f"{len(new)} new item docs; fields: {[sorted(d['data']) for d in new.values()]}")
    ok = len(new) == 2 and all(any(h["data"].get("text") == f"Added “{d['data']['text']}”"
                                   and h["data"].get("list") == "costco" and h["data"].get("by") == "claude"
                                   for h in r.new("history").values()) for d in new.values())
    yield ("Each new item has a history entry reading exactly Added “<item text>”, on costco, marked as written by claude",
           ok, f"new history texts: {[h['data'].get('text') for h in r.new('history').values()]}")
    yield ("Nothing that was already there changed: existing items, lists and history are identical",
           r.unchanged("items") and r.unchanged("lists") and r.unchanged("history"), "compared before and after")
    yield ("The page was not republished", not r.published(), f"{len(r.published())} publish calls")
    yield ("The reply is at most two lines and names the Costco list",
           len(r.reply_lines()) <= 2 and "costco" in r.reply.lower(), f"{len(r.reply_lines())} lines")


def new_list_when_nothing_close(r):
    lists = {k: v for k, v in r.new("lists").items() if re.search("hardware", str(v["data"].get("name", "")), re.I)}
    slug = next(iter(lists), None)
    top = max(v["data"]["order"] for v in r.col("before", "lists").values())
    yield ("One new list was made, named for the hardware store, ordered after the existing lists",
           len(r.new("lists")) == 1 and len(lists) == 1
           and isinstance(lists[slug]["data"].get("order"), (int, float)) and lists[slug]["data"]["order"] > top,
           f"new lists: {[(k, v['data']) for k, v in r.new('lists').items()]}")
    sponges = r.items_like("sponge")
    yield ("Sponges is on the new list, and on no other list",
           len(sponges) == 1 and slug is not None and next(iter(sponges.values()))["data"].get("list") == slug,
           f"sponge items: {[v['data'].get('list') for v in sponges.values()]}")
    kinds = [h["data"].get("type") for h in r.new("history").values()]
    yield ("History has an entry for making the list and an entry for adding the item",
           "new-list" in kinds and "add" in kinds, f"new history types: {kinds}")
    yield ("Nothing that was already there changed", r.unchanged("items") and r.unchanged("lists") and r.unchanged("history"),
           "compared before and after")
    yield ("The reply tells the user a new list was made",
           bool(re.search(r"(made|created|new|set up|started)\b.{0,60}\blist|didn.t have|did not have|no .{0,30}list", r.reply, re.I)),
           r.reply.strip()[:160])
    yield ("The page was not republished", not r.published(), f"{len(r.published())} publish calls")


def ask_when_a_list_might_match(r):
    same = all(r.col("before", c) == r.col("after", c) for c in ("items", "lists", "history"))
    yield ("Nothing was written: items, lists and history are identical to before", same, "compared before and after")
    yield ("The reply asks the user a question", "?" in r.reply, r.reply.strip()[:160])
    yield ("The reply names the Hardware list as the possible match", bool(re.search(r"hardware", r.reply, re.I)),
           r.reply.strip()[:160])
    read = any(c["tool"] == "ArtifactData" and c["args"].get("action") in ("list", "query", "get")
               and c["args"].get("collection") == "lists" for c in r.calls)
    yield ("The live lists were read before answering", read,
           f"calls: {[(c['tool'], c['args'].get('action')) for c in r.calls]}")


def duplicate_and_done(r):
    coffee, milk = r.items_like("coffee", lst="costco"), r.items_like("milk", lst="costco")
    yield ("Coffee is on the Costco list once, not twice", len(coffee) == 1 and r.unchanged("items", "c0ffe"),
           f"{len(coffee)} coffee items")
    m = r.col("after", "items").get("m1lk2")
    yield ("The existing milk item was unchecked (done false, doneAt null) instead of a second one being added",
           len(milk) == 1 and m is not None and m["data"].get("done") is False and m["data"].get("doneAt") is None,
           f"{len(milk)} milk items; m1lk2 = {m and {k: m['data'].get(k) for k in ('done', 'doneAt')}}")
    yield ("History has an uncheck entry for the milk", bool(r.history_for("uncheck", "2% milk")),
           f"new history: {[(h['data'].get('type'), h['data'].get('text')) for h in r.new('history').values()]}")
    yield ("The Costco list still has three items", len(r.items_like(".", lst="costco")) == 3,
           f"{len(r.items_like('.', lst='costco'))} items on costco")
    yield ("The reply says coffee was already on the list", bool(re.search(r"already", r.reply, re.I)),
           r.reply.strip()[:160])


def delete_is_restorable(r):
    before = r.col("before", "items")["e99gs"]
    yield ("Eggs is gone from the Shopping list", "e99gs" not in r.col("after", "items") and not r.items_like("egg"),
           f"egg items after: {list(r.items_like('egg'))}")
    yield ("Bread and Butter are untouched", r.unchanged("items", "b4ead", "bu77r"), "compared before and after")
    snaps = [h["data"].get("snapshot") for h in r.history_for("delete-item", "Eggs")]
    want = {"items": [{"id": "e99gs", **before["data"]}]}
    yield ("History has a delete entry whose snapshot can restore Eggs: its original id and every original field",
           want in snaps, f"snapshots: {json.dumps(snaps, ensure_ascii=False)[:220]}")
    yield ("The reply is at most two lines", len(r.reply_lines()) <= 2, f"{len(r.reply_lines())} lines")
    yield ("The page was not republished", not r.published(), f"{len(r.published())} publish calls")


def set_up_from_nothing(r):
    arts = r.after["artifacts"]
    yield ("Exactly one artifact was published, with a database capability",
           len(arts) == 1 and "db" in (arts[0].get("capabilities") or {}),
           f"{len(arts)} artifacts; capabilities: {[a.get('capabilities') for a in arts]}")
    html = ""
    for c in r.published():
        p = Path(c["args"].get("file_path", ""))
        for cand in (p, r.sandbox / p):
            if cand.is_file():
                html = cand.read_text(errors="replace")
    yield ("The published page does not hardcode the items; they live in the database",
           bool(html) and not re.search(r"\b(tent|stove|headlamps?)\b", html, re.I),
           "page found, no item text in it" if html and not re.search(r"\b(tent|stove|headlamps?)\b", html, re.I)
           else ("page not found" if not html else "item text found in the published HTML"))
    docs = [json.dumps(d["data"]) for a in arts for col in r.after["db"].get(a["url"], {}).values() for d in col.values()
            if "at" not in d["data"] or "type" not in d["data"]]
    found = {w: any(re.search(w, d, re.I) for d in docs) for w in ("tent", "stove", "headlamp")}
    yield ("Tent, stove and headlamps each exist as a document in the page's database", all(found.values()), str(found))
    yield ("The page was not pinned without the user being asked", not any(a.get("pinned") for a in arts),
           f"pinned: {[a.get('pinned') for a in arts]}")
    yield ("The reply gives the user the page or says how to open it, in at most five lines",
           len(r.reply_lines()) <= 5 and bool(re.search(r"claude\.ai/artifact|page|artifact|open", r.reply, re.I)),
           f"{len(r.reply_lines())} lines")


CHECKS = {
    "add-to-existing": add_to_existing,
    "new-list-when-nothing-close": new_list_when_nothing_close,
    "ask-when-a-list-might-match": ask_when_a_list_might_match,
    "duplicate-and-done": duplicate_and_done,
    "delete-is-restorable": delete_is_restorable,
    "set-up-from-nothing": set_up_from_nothing,
}


def main():
    name, fixture, run_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    r = Run(fixture, run_dir)
    r.sandbox = run_dir / "sandbox"
    exps = [{"text": t, "passed": bool(ok), "evidence": ev} for t, ok, ev in CHECKS[name](r)]
    passed = sum(e["passed"] for e in exps)
    print(json.dumps({"expectations": exps, "summary": {
        "passed": passed, "failed": len(exps) - passed, "total": len(exps),
        "pass_rate": round(passed / len(exps), 4)}}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
