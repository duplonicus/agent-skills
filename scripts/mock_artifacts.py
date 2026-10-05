#!/usr/bin/env python3
"""A local stand-in for the Artifact and ArtifactData tools, for evals.

Speaks MCP over stdio with no dependencies. All state lives in one JSON file
(path in the MOCK_STATE environment variable), so an eval can seed it before a
run and inspect it afterwards:

    {"artifacts": [{"url", "title", "capabilities", "published_from"}],
     "db": {"<url>": {"<collection>": {"<doc_id>": {"data": {...}, "version": N}}}},
     "calls": [{"tool", "args"}]}

The database follows the rules that matter to a skill: every document has a
version, a write to an existing document needs a matching `if_version`, and a
batch applies all of its writes or none of them.
"""
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

STATE = Path(os.environ.get("MOCK_STATE", "mock_state.json"))

TOOLS = [
    {
        "name": "Artifact",
        "description": (
            "Publishes an HTML file as an Artifact: a private web page at a claude.ai URL. "
            "action 'publish' (default) takes file_path, plus icon, an optional description, and "
            "capabilities (for example {\"db\": {}} to give the page a shared database); with url it "
            "updates that artifact in place. action 'list' returns the person's artifacts (title and "
            "URL), newest first. action 'read' takes url. action 'open' takes url and shows the "
            "person that artifact. action 'pin' / 'unpin' takes url; pin only when the person asks."),
        "inputSchema": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["publish", "list", "read", "open", "pin", "unpin"]},
            "file_path": {"type": "string"}, "url": {"type": "string"}, "title": {"type": "string"},
            "icon": {"type": "string"}, "description": {"type": "string"},
            "capabilities": {"type": "object"}, "scope": {"type": "string"},
            "limit": {"type": "integer"}}},
    },
    {
        "name": "ArtifactData",
        "description": (
            "The shared database of a published artifact's page; every call takes the artifact's url. "
            "Reads: 'get' (collection + doc_id), 'list' (collection), 'query' (collection + "
            "query.where, a list of [field, operator, value] triples). Every document read shows its "
            "version. Writes: 'set' replaces a document, 'update' merges fields into it (collection, "
            "doc_id, data), 'delete' removes it, and 'batch' applies up to 50 writes at once, passed "
            "in `writes` as {op, collection, doc_id, data, if_version} entries, all or nothing. Pass "
            "the version you last read as if_version on every write to a document that already "
            "exists; such a write is refused without it, and fails if the document has changed. Omit "
            "it only when creating a document."),
        "inputSchema": {"type": "object", "required": ["action", "url"], "properties": {
            "action": {"type": "string",
                       "enum": ["get", "list", "query", "set", "update", "delete", "batch"]},
            "url": {"type": "string"}, "collection": {"type": "string"},
            "doc_id": {"type": "string"}, "data": {"type": "object"},
            "if_version": {"type": "integer"},
            "query": {"type": "object", "properties": {
                "where": {"type": "array"}, "limit": {"type": "integer"}}},
            "writes": {"type": "array", "maxItems": 50, "items": {"type": "object"}}}},
    },
]


class Refused(Exception):
    pass


def load():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"artifacts": [], "db": {}, "calls": []}


def save(state):
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def find(state, url):
    for a in state["artifacts"]:
        if a["url"] == url:
            return a
    raise Refused(f"No artifact at {url}. Use Artifact with action 'list' to find the person's artifacts.")


def artifact(state, a):
    action = a.get("action") or "publish"
    if action == "list":
        return {"artifacts": [{"title": x["title"], "url": x["url"]} for x in state["artifacts"]]}
    if action == "publish":
        path = Path(a.get("file_path") or "")
        if not path.is_file():
            raise Refused(f"file_path does not exist: {path}")
        content = path.read_bytes()
        record = {"title": a.get("title") or path.stem, "capabilities": a.get("capabilities") or {},
                  "icon": a.get("icon"), "description": a.get("description"),
                  "published_from": str(path), "sha256": hashlib.sha256(content).hexdigest(),
                  "pinned": False}
        if a.get("url"):
            find(state, a["url"]).update(record)
            return {"url": a["url"], "updated": True}
        record["url"] = f"https://claude.ai/artifact/mock-{len(state['artifacts']) + 1:03d}"
        state["artifacts"].append(record)
        state["db"].setdefault(record["url"], {})
        return {"url": record["url"], "visibility": "private"}
    art = find(state, a.get("url"))
    if action in ("pin", "unpin"):
        art["pinned"] = action == "pin"
        return {"url": art["url"], "pinned": art["pinned"]}
    if action == "open":
        return {"url": art["url"], "opened": True}
    return {"url": art["url"], "title": art["title"], "capabilities": art.get("capabilities", {})}


OPS = {"==": lambda x, y: x == y, "eq": lambda x, y: x == y,
       "!=": lambda x, y: x != y, "ne": lambda x, y: x != y}


def apply_write(db, w):
    col = db.setdefault(w["collection"], {})
    doc_id, op = w["doc_id"], w["op"]
    cur = col.get(doc_id)
    pin = w.get("if_version")
    if cur is not None:
        if pin is None:
            raise Refused(f"{w['collection']}/{doc_id} already exists: read it and pass its version as if_version.")
        if pin != cur["version"]:
            raise Refused(f"{w['collection']}/{doc_id} has changed: current version is {cur['version']}, not {pin}.")
    elif op in ("update", "delete") or pin is not None:
        raise Refused(f"{w['collection']}/{doc_id} does not exist.")
    if op == "delete":
        del col[doc_id]
        return {"doc_id": doc_id, "deleted": True}
    if not isinstance(w.get("data"), dict):
        raise Refused(f"{op} on {w['collection']}/{doc_id} needs a data object.")
    data = dict(cur["data"]) if (cur and op == "update") else {}
    data.update(w["data"])
    col[doc_id] = {"data": data, "version": (cur["version"] + 1) if cur else 1}
    return {"doc_id": doc_id, "version": col[doc_id]["version"]}


def artifact_data(state, a):
    find(state, a.get("url"))
    db = state["db"].setdefault(a["url"], {})
    action = a["action"]
    docs = lambda col: [{"id": k, "data": v["data"], "version": v["version"]}
                        for k, v in db.get(col, {}).items()]
    if action == "get":
        doc = db.get(a["collection"], {}).get(a["doc_id"])
        if doc is None:
            raise Refused(f"{a['collection']}/{a['doc_id']} not found.")
        return {"id": a["doc_id"], **doc}
    if action == "list":
        return {"documents": docs(a["collection"])}
    if action == "query":
        out = docs(a["collection"])
        for field, op, value in (a.get("query") or {}).get("where", []):
            if op not in OPS:
                raise Refused(f"Operator {op} is not supported by this mock.")
            out = [d for d in out if OPS[op](d["data"].get(field), value)]
        return {"documents": out}
    if action == "batch":
        writes = a.get("writes") or []
        if not 1 <= len(writes) <= 50:
            raise Refused("batch takes 1 to 50 writes.")
        ids = [(w["collection"], w["doc_id"]) for w in writes]
        if len(set(ids)) != len(ids):
            raise Refused("Each document may be addressed at most once in a batch.")
        trial = copy.deepcopy(db)
        results = [apply_write(trial, w) for w in writes]  # raises before anything is kept
        state["db"][a["url"]] = trial
        return {"applied": len(results), "atomic": True, "results": results}
    if action in ("set", "update", "delete"):
        return apply_write(db, {"op": action, "collection": a["collection"], "doc_id": a["doc_id"],
                                "data": a.get("data"), "if_version": a.get("if_version")})
    raise Refused(f"Unknown action {action}.")


def call(name, args):
    state = load()
    state["calls"].append({"tool": name, "args": args})
    try:
        result = artifact(state, args) if name == "Artifact" else artifact_data(state, args)
        text, is_error = json.dumps(result, ensure_ascii=False), False
    except Refused as e:
        text, is_error = f"Refused, nothing was written: {e}", True
    except (KeyError, TypeError, ValueError) as e:
        text, is_error = f"Bad request, nothing was written: {e!r}", True
    save(state)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method, mid = msg.get("method"), msg.get("id")
        if mid is None:
            continue  # a notification: nothing to answer
        if method == "initialize":
            result = {"protocolVersion": msg["params"].get("protocolVersion", "2024-11-05"),
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "mock-artifacts", "version": "1.0"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = call(msg["params"]["name"], msg["params"].get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": mid,
                              "error": {"code": -32601, "message": f"Unknown method {method}"}}), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}), flush=True)


if __name__ == "__main__":
    main()
