"""Browser tests for the due-date parts of skills/todo-list/assets/todo-list.html.

The page is loaded as published (wrapped in the same skeleton) against an
in-memory stand-in for the artifact database, with the clock pinned, so the
badge wording and the writes the page makes can be asserted exactly.
Needs Playwright: uv run --with pytest --with playwright pytest tests
"""
import json
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PAGE = Path(__file__).resolve().parent.parent / "skills" / "todo-list" / "assets" / "todo-list.html"
SKELETON = ('<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,'
            'initial-scale=1"><style>:root{color-scheme:light}body{margin:0}[hidden]{display:none!important}'
            "</style></head><body>%s</body></html>")
NOW = "2026-10-10T14:00:00"   # a Saturday, local time

FAKE_DB = """
(seed => {
  const cols = { lists: new Map(), items: new Map(), history: new Map() }, subs = { lists: [], items: [], history: [] };
  for (const [c, docs] of Object.entries(seed)) for (const [id, d] of Object.entries(docs)) cols[c].set(id, d);
  let n = 0;
  const emit = c => { const s = { docs: [...cols[c]].map(([id, d]) => ({ id, data: () => ({ ...d }) })) }; subs[c].forEach(f => f(s)); };
  const ref = (c, id) => ({ id,
    set: async d => { cols[c].set(id, { ...d }); emit(c); },
    update: async d => { if (!cols[c].has(id)) throw { code: "not_found" }; cols[c].set(id, { ...cols[c].get(id), ...d }); emit(c); },
    delete: async () => { cols[c].delete(id); emit(c); } });
  const db = {
    collection: c => ({ onSnapshot: f => { subs[c].push(f); setTimeout(() => emit(c), 0); },
      add: async d => { const r = ref(c, "p" + (++n)); await r.set(d); return r; }, doc: id => ref(c, id || "p" + (++n)) }),
    doc: path => { const [c, id] = path.split("/"); return ref(c, id); } };
  window.__cols = cols;
  window.claude = { use: async name => name === "db" ? db : { can: async () => true } };
})(%s);
"""


def base(doc_id, text, order, **extra):
    return doc_id, {"list": "todo", "text": text, "done": False, "created": "2026-10-01T00:00:00.000Z",
                    "doneAt": None, "order": order, **extra}


SEED = {
    "lists": {"todo": {"name": "Todo", "order": 1000}},
    "items": dict([
        base("plain", "Buy stamps", 1),
        base("timed", "Call dentist", 2, due="2026-10-16T15:00", calEvent="ev1", calDue="2026-10-16T15:00"),
        base("late", "Renew passport", 3, due="2026-10-08"),
        base("moved", "Book flights", 4, due="2026-10-11", calEvent="ev2", calDue="2026-10-12"),
        base("soon", "Pay rent", 5, due="2026-10-10T18:30"),
        base("fin", "File taxes", 6, due="2026-10-09", done=True, doneAt="2026-10-09T12:00:00.000Z",
             calEvent="ev3", calDue="2026-10-09"),
    ]),
    "history": {},
}


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def open_page(browser, scheme="light", seed=SEED, sortable=False):
    ctx = browser.new_context(locale="en-US", timezone_id="America/Toronto", color_scheme=scheme,
                              viewport={"width": 400, "height": 900})
    page = ctx.new_page()
    if not sortable:   # only the drag tests need the drag library, and with it the network
        page.route("https://cdn.jsdelivr.net/**", lambda r: r.abort())
    page.clock.install(time=NOW)
    page.add_init_script(FAKE_DB % json.dumps(seed))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("http://todo.test/", lambda r: r.fulfill(content_type="text/html", body=SKELETON % PAGE.read_text()))
    page.goto("http://todo.test/")
    page.wait_for_selector("li .label")
    page.errors = errors
    return page


def rows(page):
    return page.evaluate("""() => [...document.querySelectorAll('#main li')].map(li => ({
        text: li.querySelector('.label')?.textContent, due: li.querySelector('.due')?.textContent ?? null,
        cls: li.querySelector('.due')?.className ?? null, bell: !!li.querySelector('.due svg') }))""")


@pytest.mark.parametrize("due, state, text", [
    ("2026-10-10", "today", "Due today"),
    ("2026-10-10T14:01", "today", "Due today, 2:01 PM"),
    ("2026-10-10T14:00", "over", "Overdue · today, 2:00 PM"),
    ("2026-10-10T09:05", "over", "Overdue · today, 9:05 AM"),
    ("2026-10-09", "over", "Overdue · yesterday"),
    ("2026-10-01", "over", "Overdue · Oct 1"),
    ("2026-10-11T15:00", "later", "Due tomorrow, 3:00 PM"),
    ("2026-10-14", "later", "Due Wednesday"),
    ("2026-10-16", "later", "Due Friday"),
    ("2026-10-17", "later", "Due Oct 17"),
    ("2027-01-05T00:00", "later", "Due Jan 5, 2027, 12:00 AM"),
])
def test_badge_wording_and_urgency(browser, due, state, text):
    page = open_page(browser)
    info = page.evaluate("due => window.__dueInfo(due, new Date())", due)
    assert (info["state"], info["text"]) == (state, text)


@pytest.mark.parametrize("due", ["", None, "tomorrow", "2026-02-30", "2026-13-01", "2026-10-10T24:00",
                                 "2026-10-10T15:00Z", "2026-10-10 15:00"])
def test_values_that_are_not_dates_show_no_badge(browser, due):
    page = open_page(browser)
    assert page.evaluate("due => window.__dueInfo(due, new Date())", due) is None


def test_rows_show_the_due_line_and_keep_their_order(browser):
    page = open_page(browser)
    assert rows(page) == [
        {"text": "Buy stamps", "due": None, "cls": None, "bell": False},
        {"text": "Call dentist", "due": "Due Friday, 3:00 PM", "cls": "due later", "bell": True},
        {"text": "Renew passport", "due": "Overdue · Oct 8", "cls": "due over", "bell": False},
        # The date was changed after the reminder was made, so the page must not claim one.
        {"text": "Book flights", "due": "Due tomorrow", "cls": "due later", "bell": False},
        {"text": "Pay rent", "due": "Due today, 6:30 PM", "cls": "due today", "bell": False},
        {"text": "File taxes", "due": "Was due yesterday", "cls": "due", "bell": False},
    ]
    assert page.errors == []


def test_a_badge_goes_overdue_while_the_page_sits_open(browser):
    page = open_page(browser)
    page.clock.fast_forward("04:31:00")   # 6:31 PM, a minute after rent was due
    assert [r for r in rows(page) if r["text"] == "Pay rent"] == [
        {"text": "Pay rent", "due": "Overdue · today, 6:30 PM", "cls": "due over", "bell": False}]


def test_setting_a_due_date_on_the_page_saves_it_and_logs_it(browser):
    page = open_page(browser)
    before = [r["text"] for r in rows(page)]
    page.click("li:has-text('Buy stamps') .text")
    page.fill("#due-date-plain", "2026-10-16")
    page.fill("#due-time-plain", "15:00")
    page.press("#due-time-plain", "Enter")
    page.wait_for_selector("li:has-text('Buy stamps') .due")
    item = page.evaluate("() => window.__cols.items.get('plain')")
    assert item["due"] == "2026-10-16T15:00" and item["text"] == "Buy stamps"
    assert "calEvent" not in item, "the page cannot make a reminder and must not claim one"
    assert page.evaluate("() => [...window.__cols.history.values()].map(h => [h.type, h.text, h.by])") == [
        ["edit", "Set “Buy stamps” due Friday, 3:00 PM", "page"]]
    after = rows(page)
    assert [r["text"] for r in after] == before, "a due date must not move the item"
    assert after[0] == {"text": "Buy stamps", "due": "Due Friday, 3:00 PM", "cls": "due later", "bell": False}


def test_a_date_with_no_time_is_saved_as_a_date(browser):
    page = open_page(browser)
    page.click("li:has-text('Buy stamps') .text")
    page.fill("#due-date-plain", "2026-10-20")
    page.click(".duerow >> text=Save")
    page.wait_for_selector("li:has-text('Buy stamps') .due")
    assert page.evaluate("() => window.__cols.items.get('plain').due") == "2026-10-20"


def test_changing_the_date_keeps_the_event_link_but_drops_the_bell(browser):
    page = open_page(browser)
    page.click("li:has-text('Call dentist') .text")
    assert "A reminder is on your calendar" in page.inner_text(".duerow .hint")
    page.fill("#due-date-timed", "2026-10-19")
    page.press("#due-date-timed", "Enter")
    page.wait_for_function("() => window.__cols.items.get('timed').due === '2026-10-19T15:00'")
    item = page.evaluate("() => window.__cols.items.get('timed')")
    # The stale pair is how the assistant later sees that event ev1 needs moving.
    assert (item["calEvent"], item["calDue"]) == ("ev1", "2026-10-16T15:00")
    assert [r["bell"] for r in rows(page) if r["text"] == "Call dentist"] == [False]


def test_removing_the_due_date(browser):
    page = open_page(browser)
    page.click("li:has-text('Renew passport') .text")
    page.click("text=No due date")
    page.wait_for_function("() => window.__cols.items.get('late').due === null")
    assert [r["due"] for r in rows(page) if r["text"] == "Renew passport"] == [None]
    assert page.evaluate("() => [...window.__cols.history.values()].map(h => h.text)") == [
        "Removed the due date from “Renew passport”"]


def test_editing_only_the_text_leaves_the_due_date_alone(browser):
    page = open_page(browser)
    page.click("li:has-text('Call dentist') .text")
    page.fill("#edit-timed", "Call the dentist")
    page.press("#edit-timed", "Enter")
    page.wait_for_function("() => window.__cols.items.get('timed').text === 'Call the dentist'")
    assert page.evaluate("() => window.__cols.items.get('timed').due") == "2026-10-16T15:00"
    assert page.evaluate("() => [...window.__cols.history.values()].map(h => h.text)") == [
        "Changed “Call dentist” to “Call the dentist”"]


def test_escape_saves_nothing(browser):
    page = open_page(browser)
    page.click("li:has-text('Buy stamps') .text")
    page.fill("#due-date-plain", "2026-10-16")
    page.press("#due-date-plain", "Escape")
    page.wait_for_selector("li:has-text('Buy stamps') .label")
    assert "due" not in page.evaluate("() => window.__cols.items.get('plain')")
    assert page.evaluate("() => window.__cols.history.size") == 0


@pytest.mark.parametrize("scheme, danger, accent, muted", [
    ("light", "rgb(179, 38, 30)", "rgb(201, 100, 66)", "rgb(107, 106, 101)"),
    ("dark", "rgb(242, 113, 95)", "rgb(217, 119, 87)", "rgb(166, 163, 155)"),
])
def test_badge_colours_come_from_the_theme(browser, scheme, danger, accent, muted):
    page = open_page(browser, scheme)
    colour = lambda text: page.evaluate(
        "t => getComputedStyle([...document.querySelectorAll('li')].find(li => li.textContent.includes(t))"
        ".querySelector('.due')).color", text)
    assert colour("Renew passport") == danger
    assert colour("Pay rent") == accent
    assert colour("Call dentist") == muted


def test_nothing_overflows_at_phone_width(browser):
    page = open_page(browser)
    page.click("li:has-text('Call dentist') .text")
    page.wait_for_selector("#due-date-timed")
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")


# ---------- handles on done items ----------

DONE_SEED = {
    "lists": {"todo": {"name": "Todo", "order": 1000}, "shop": {"name": "Shop", "order": 2000}},
    "items": dict([
        base("open1", "Still open", 1),
        base("d1", "Done first", 2, done=True, doneAt="2026-10-07T12:00:00.000Z"),
        base("d2", "Done second", 3, done=True, doneAt="2026-10-08T12:00:00.000Z"),
        base("d3", "Done third", 4, done=True, doneAt="2026-10-09T12:00:00.000Z"),
    ]),
    "history": {},
}
DONE_TEXTS = "() => [...document.querySelectorAll('#main li.done .label')].map(e => e.textContent)"


def drag(page, text, target):
    grip = page.locator(f"li:has-text('{text}') .grip").bounding_box()
    to = page.locator(target).bounding_box()
    x, y = grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2
    tx, ty = to["x"] + to["width"] / 2, to["y"] + to["height"] * 0.8
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 11):
        page.mouse.move(x + (tx - x) * i / 10, y + (ty - y) * i / 10)
    page.mouse.up()


def drag_page(browser):
    page = open_page(browser, seed=DONE_SEED, sortable=True)
    if not page.evaluate("() => !!window.Sortable"):
        pytest.skip("the drag library did not load from its CDN (no network)")
    return page


def test_done_items_have_a_handle_and_sort_newest_first(browser):
    page = open_page(browser, seed=DONE_SEED)
    assert page.evaluate(DONE_TEXTS) == ["Done third", "Done second", "Done first"]
    assert page.evaluate("() => [...document.querySelectorAll('#main li')].map(li => !!li.querySelector('.grip'))") == [True] * 4


def test_a_dragged_done_item_keeps_its_place(browser):
    seed = json.loads(json.dumps(DONE_SEED))
    # As the page stores a drag of "Done first" to between the other two: halfway between their keys.
    seed["items"]["d1"]["doneOrder"] = -(1791547200000 + 1791460800000) / 2
    page = open_page(browser, seed=seed)
    assert page.evaluate(DONE_TEXTS) == ["Done third", "Done first", "Done second"]


def test_checking_or_unchecking_forgets_a_dragged_position(browser):
    seed = json.loads(json.dumps(DONE_SEED))
    seed["items"]["d1"]["doneOrder"] = -1e15   # dragged to the very top
    page = open_page(browser, seed=seed)
    assert page.evaluate(DONE_TEXTS)[0] == "Done first"
    page.click("li:has-text('Done first') .check")
    page.wait_for_function("() => window.__cols.items.get('d1').done === false")
    assert page.evaluate("() => window.__cols.items.get('d1').doneOrder") is None
    page.click("li:has-text('Still open') .check")
    page.wait_for_function("() => window.__cols.items.get('open1').done === true")
    assert page.evaluate(DONE_TEXTS) == ["Still open", "Done third", "Done second"]


def test_dragging_a_done_item_reorders_the_done_section(browser):
    page = drag_page(browser)
    drag(page, "Done third", "li:has-text('Done first')")
    page.wait_for_function("() => typeof window.__cols.items.get('d3').doneOrder === 'number'")
    assert page.evaluate(DONE_TEXTS) == ["Done second", "Done first", "Done third"]
    items = page.evaluate("() => Object.fromEntries(window.__cols.items)")
    assert all("doneOrder" not in items[k] for k in ("d1", "d2", "open1")), "only the dragged item is written"
    assert items["d3"]["done"] is True and items["d3"]["order"] == 4
    assert page.errors == []


def test_dragging_a_done_item_onto_a_tab_moves_it_to_that_list(browser):
    page = drag_page(browser)
    drag(page, "Done second", ".tab[data-id='shop']")
    page.wait_for_function("() => window.__cols.items.get('d2').list === 'shop'")
    assert page.evaluate("() => window.__cols.items.get('d2').done") is True
    assert page.evaluate(DONE_TEXTS) == ["Done third", "Done first"]
