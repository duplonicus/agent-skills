#!/usr/bin/env python3
"""A local stand-in for a shell on the user's machine, for evals.

Speaks MCP over stdio with no dependencies. It offers one tool, `run`, which
records the command it was given and answers from a script in one JSON file
(path in the MOCK_STATE environment variable). Nothing is executed anywhere,
so an eval can judge what the agent tried to run without anything being at risk.

State file:

    {"responses": [{"match": "^date\\b", "output": "Wed Mar 11 14:32:07 EDT 2026", "exit": 0}],
     "events": []}                      filled in by this server

`match` is a regular expression searched in the command; the first one that
matches answers it. A command nothing matches gets empty output and exit 0,
which is what a command that changes something usually prints.
"""
import json
import os
import re
import sys
from pathlib import Path

STATE = Path(os.environ.get("MOCK_STATE", "mock_shell.json"))

TOOLS = [
    {"name": "run", "description": "Run one shell command on the user's machine and return its output and exit code.",
     "inputSchema": {"type": "object", "required": ["command"],
                     "properties": {"command": {"type": "string", "description": "The command line to run"}}}},
]


def run(args):
    command = args["command"]
    state = json.loads(STATE.read_text())
    answer = next((r for r in state.get("responses", []) if re.search(r["match"], command)), {})
    output, code = answer.get("output", ""), answer.get("exit", 0)
    state.setdefault("events", []).append({"t": "run", "command": command, "exit": code})
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    return {"content": [{"type": "text", "text": f"{output}\n[exit {code}]".lstrip("\n")}], "isError": False}


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
                      "serverInfo": {"name": "mock-shell", "version": "1.0"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call" and msg["params"]["name"] == "run":
            try:
                result = run(msg["params"].get("arguments") or {})
            except (KeyError, TypeError, re.error) as e:
                result = {"content": [{"type": "text", "text": f"Bad request: {e!r}"}], "isError": True}
        elif method == "ping":
            result = {}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": mid,
                              "error": {"code": -32601, "message": f"Unknown method {method}"}}), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}), flush=True)


if __name__ == "__main__":
    main()
