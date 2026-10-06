#!/usr/bin/env python3
"""A local stand-in for browser-automation tools, for evals.

Speaks MCP over stdio with no dependencies. It serves a small fake web app from
one JSON file (path in the MOCK_STATE environment variable) and records
everything the agent does to it, so an eval can judge behaviour from the
record: what was clicked, what was typed, what was highlighted, where it went.

State file:

    {"start_url": "https://console.acme.test/dashboard",
     "pages": {"/dashboard": {
         "title": "...", "text": "...",
         "redirect": "/login",                      (optional)
         "overlay": {"text": "...", "elements": [...]},   (optional; hides the page until dismissed)
         "elements": [{"ref": "e1", "label": "Create user", "role": "button",
                       "kind": "nav" | "view" | "action" | "field",
                       "goto": "/users",            (nav)
                       "category": "create",        (action: what kind of change it makes)
                       "credential": true}]}},      (field: a password, code or key)
     "tabs": [{"id": 1, "url": "...", "title": "..."}],   the user's own tabs
     "events": []}                                         filled in by this server

Element kinds: "nav" and "view" are read-only; "action" changes state (and is
recorded with its category); "field" accepts typing. Nothing is really changed
anywhere: an action just records that it was triggered.
"""
import json
import os
import re
import sys
from pathlib import Path

STATE = Path(os.environ.get("MOCK_STATE", "mock_browser.json"))
ORIGIN_RE = re.compile(r"^https?://[^/]+")

TAB = {"tabId": {"type": "integer", "description": "Tab to act on (from tabs_context_mcp or tabs_create_mcp)"}}
TOOLS = [
    {"name": "tabs_context_mcp", "description": "List the user's open browser tabs. Call this first.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "tabs_create_mcp", "description": "Open a new empty tab and return its id.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "navigate", "description": "Go to a URL in a tab.",
     "inputSchema": {"type": "object", "required": ["tabId", "url"],
                     "properties": {**TAB, "url": {"type": "string"}}}},
    {"name": "get_page_text", "description": "Read the visible text of the page in a tab.",
     "inputSchema": {"type": "object", "required": ["tabId"], "properties": TAB}},
    {"name": "read_page", "description": "List the page's interactive elements with a ref for each (use the ref to click or type).",
     "inputSchema": {"type": "object", "required": ["tabId"], "properties": TAB}},
    {"name": "find", "description": "Find elements on the page by a description or label; returns matching refs.",
     "inputSchema": {"type": "object", "required": ["tabId", "query"],
                     "properties": {**TAB, "query": {"type": "string"}}}},
    {"name": "javascript_tool", "description": "Run JavaScript in the page and return the result of the last expression.",
     "inputSchema": {"type": "object", "required": ["tabId", "text"],
                     "properties": {**TAB, "text": {"type": "string", "description": "The JavaScript to run"}}}},
    {"name": "computer", "description": (
        "Mouse and keyboard. action 'left_click' with `ref` clicks that element; 'type' with `text` types "
        "into the element last clicked (or `ref`); 'key' with `text` presses a key; 'scroll' scrolls; "
        "'screenshot' captures the page."),
     "inputSchema": {"type": "object", "required": ["tabId", "action"],
                     "properties": {**TAB, "action": {"type": "string", "enum": ["left_click", "type", "key", "scroll", "screenshot"]},
                                    "ref": {"type": "string"}, "text": {"type": "string"},
                                    "coordinate": {"type": "array", "items": {"type": "number"}}}}},
    {"name": "form_input", "description": "Set the value of a form field by ref.",
     "inputSchema": {"type": "object", "required": ["tabId", "ref", "value"],
                     "properties": {**TAB, "ref": {"type": "string"}, "value": {"type": "string"}}}},
]


class Refused(Exception):
    pass


class Browser:
    def __init__(self):
        self.s = json.loads(STATE.read_text())
        self.s.setdefault("events", [])
        self.s.setdefault("tabs", [])
        self.s.setdefault("agent_tabs", {})
        self.s.setdefault("dismissed", [])
        self.origin = ORIGIN_RE.match(self.s["start_url"]).group(0)

    def save(self):
        STATE.write_text(json.dumps(self.s, indent=2, ensure_ascii=False))

    def log(self, **event):
        self.s["events"].append(event)

    # --- pages -------------------------------------------------------------
    def tab(self, tab_id):
        tab = self.s["agent_tabs"].get(str(tab_id))
        if tab is None:
            if any(t["id"] == tab_id for t in self.s["tabs"]):
                # The user's own tab: usable, but recorded, because a tour should leave those alone.
                tab = self.s["agent_tabs"][str(tab_id)] = {"path": None, "focus": None, "users_tab": True}
            else:
                raise Refused(f"No tab {tab_id}. Call tabs_context_mcp, or tabs_create_mcp for a new tab.")
        return tab

    def page(self, tab):
        if tab["path"] is None:
            raise Refused("This tab is empty. Navigate to a URL first.")
        return self.s["pages"][tab["path"]]

    def go(self, tab, path, via):
        path = path.split("?")[0].split("#")[0].rstrip("/") or "/"
        known = self.s["pages"]
        if path not in known:
            self.log(t="navigate", path=path, via=via, found=False)
            raise Refused(f"404: {self.origin}{path} does not exist in this app.")
        if known[path].get("redirect"):
            self.log(t="navigate", path=path, via=via, found=True, redirected_to=known[path]["redirect"])
            path = known[path]["redirect"]
        else:
            self.log(t="navigate", path=path, via=via, found=True)
        tab["path"], tab["focus"] = path, None

    def visible(self, tab):
        """(text, elements) the user can currently see: the overlay if one is up, else the page."""
        page = self.page(tab)
        overlay = page.get("overlay")
        if overlay and tab["path"] not in self.s["dismissed"]:
            return overlay["text"], overlay["elements"], True
        return page["text"], page["elements"], False

    def element(self, tab, ref):
        _, elements, _ = self.visible(tab)
        for el in elements:
            if el["ref"] == ref:
                return el
        raise Refused(f"No element with ref {ref} on this page. Call read_page for the current refs.")

    # --- tools -------------------------------------------------------------
    def tabs_context_mcp(self, a):
        mine = [{"id": int(k), "url": self.origin + v["path"] if v["path"] else "about:blank", "opened_by": "assistant"}
                for k, v in self.s["agent_tabs"].items() if not v.get("users_tab")]
        return {"tabs": [dict(t, opened_by="user") for t in self.s["tabs"]] + mine}

    def tabs_create_mcp(self, a):
        tab_id = 100 + len(self.s["agent_tabs"])
        self.s["agent_tabs"][str(tab_id)] = {"path": None, "focus": None}
        self.log(t="new_tab", tab=tab_id)
        return {"tabId": tab_id, "url": "about:blank"}

    def navigate(self, a):
        tab = self.tab(a["tabId"])
        url = a["url"]
        if ORIGIN_RE.match(url) and not url.startswith(self.origin):
            self.log(t="navigate", url=url, via="url", external=True)
            raise Refused(f"{url} could not be loaded: this environment only reaches {self.origin}.")
        self.go(tab, ORIGIN_RE.sub("", url) or "/", "url")
        return {"url": self.origin + tab["path"], "title": self.page(tab)["title"]}

    def get_page_text(self, a):
        tab = self.tab(a["tabId"])
        text, elements, overlaid = self.visible(tab)
        self.log(t="read", path=tab["path"], tool="get_page_text")
        controls = ", ".join(f"[{el['label']}]" for el in elements)
        note = "\n(A dialog covers the rest of the page.)" if overlaid else ""
        return f"{self.page(tab)['title']}\nURL: {self.origin}{tab['path']}\n\n{text}{note}\n\nControls: {controls}"

    def read_page(self, a):
        tab = self.tab(a["tabId"])
        _, elements, overlaid = self.visible(tab)
        self.log(t="read", path=tab["path"], tool="read_page")
        lines = [f"{el['role']} \"{el['label']}\" [ref={el['ref']}]" for el in elements]
        return ("dialog (covers the page)\n" if overlaid else "") + "\n".join(lines)

    def find(self, a):
        tab = self.tab(a["tabId"])
        _, elements, _ = self.visible(tab)
        words = [w for w in re.findall(r"[a-z0-9]+", a["query"].lower()) if len(w) > 2]
        hits = [el for el in elements if any(w in el["label"].lower() for w in words)]
        return {"matches": [{"ref": el["ref"], "role": el["role"], "label": el["label"]} for el in hits]}

    def javascript_tool(self, a):
        tab = self.tab(a["tabId"])
        code = a["text"]
        _, elements, _ = self.visible(tab)
        spotlight = re.search(r"target:\s*(['\"])(.*?)\1\s*,\s*label:\s*(['\"])(.*?)\3", code)
        if spotlight and "data-tour-hl" in code:
            target, label = spotlight.group(2), spotlight.group(4)
            if target == "__CLEAR__":
                self.log(t="spotlight", target=target, cleared=True)
                return "cleared"
            want = target.lower().strip()
            hits = sorted((el for el in elements if want and want in el["label"].lower()),
                          key=lambda el: (el["label"].lower() != want, len(el["label"])))
            if not hits:
                # spotlight.js falls back to headings and other visible text when no control matches.
                text, _, _ = self.visible(tab)
                line = next((ln.strip() for ln in text.splitlines() if want and want in ln.lower()), None)
                if line is None:
                    self.log(t="spotlight", target=target, label=label, found=False, path=tab["path"])
                    return "not found"
                self.log(t="spotlight", target=target, label=label, found=True, element=f"text: {line[:60]}",
                         kind="text", category=None, path=tab["path"])
                return f"ok: {label} '{line[:60].lower()}'"
            el = hits[0]
            self.log(t="spotlight", target=target, label=label, found=True, element=el["label"],
                     kind=el["kind"], category=el.get("category"), path=tab["path"])
            return f"ok: {label} '{el['label'].lower()}'"
        # Any other script: record what it tries to do. Nothing is executed.
        flags = {
            "clicks": bool(re.search(r"\.click\s*\(|dispatchEvent|\.submit\s*\(", code)),
            "sets_value": bool(re.search(r"\.value\s*=|setAttribute\(\s*['\"]value", code)),
            "styles": bool(re.search(r"outline|border|boxShadow|box-shadow|background", code)),
        }
        named = [el["label"] for el in elements if el["label"].lower() in code.lower()]
        self.log(t="js", code=code[:600], path=tab["path"], named=named, **flags)
        return "undefined"

    def computer(self, a):
        tab = self.tab(a["tabId"])
        action = a["action"]
        if action == "screenshot":
            self.log(t="read", path=tab["path"], tool="screenshot")
            return "Screenshots are not available in this environment. Use get_page_text or read_page."
        if action == "scroll":
            return "scrolled"
        if action == "key":
            self.log(t="key", text=a.get("text", ""), path=tab["path"], focus=tab["focus"])
            return f"pressed {a.get('text', '')}"
        if action == "type":
            ref = a.get("ref") or tab["focus"]
            if not ref:
                raise Refused("Nothing is focused. Click a field first, or pass its ref.")
            return self.type_into(tab, self.element(tab, ref), a.get("text", ""))
        if action == "left_click":
            if not a.get("ref"):
                self.log(t="click", element=None, coordinate=a.get("coordinate"), path=tab["path"])
                raise Refused("Click by ref in this environment: call read_page and pass the element's ref.")
            return self.click(tab, self.element(tab, a["ref"]))
        raise Refused(f"Unknown action {action}.")

    def form_input(self, a):
        tab = self.tab(a["tabId"])
        return self.type_into(tab, self.element(tab, a["ref"]), a["value"])

    def type_into(self, tab, el, text):
        if el["kind"] != "field":
            raise Refused(f"\"{el['label']}\" is not a text field.")
        self.log(t="type", element=el["label"], text=text, credential=bool(el.get("credential")), path=tab["path"])
        return f"typed into \"{el['label']}\""

    def click(self, tab, el):
        self.log(t="click", element=el["label"], kind=el["kind"], category=el.get("category"), path=tab["path"])
        if el["kind"] == "field":
            tab["focus"] = el["ref"]
            return f"focused \"{el['label']}\""
        if el["kind"] == "nav":
            self.go(tab, el["goto"], "click")
            return f"opened {self.page(tab)['title']}"
        if el["kind"] == "view":
            return el.get("shows", f"\"{el['label']}\" expanded.")
        # An action: it would change something. Record it; say it happened.
        if el.get("dismisses"):
            self.s["dismissed"].append(tab["path"])
        return el.get("result", f"Done: {el['label']}.")


def call(name, args):
    browser = Browser()
    try:
        result = getattr(browser, name)(args)
        text, is_error = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False), False
    except Refused as e:
        text, is_error = str(e), True
    except (KeyError, TypeError, ValueError) as e:
        text, is_error = f"Bad request: {e!r}", True
    browser.save()
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def main():
    names = {t["name"] for t in TOOLS}
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
                      "serverInfo": {"name": "mock-browser", "version": "1.0"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call" and msg["params"]["name"] in names:
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
