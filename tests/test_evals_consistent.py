"""evals.json is what people read; check.py is what grades. They must not drift."""
import importlib.util
import json
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "todo-list"


def test_todo_list_expectations_match_the_checker():
    spec = importlib.util.spec_from_file_location("check", SKILL / "evals" / "check.py")
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    evals = json.loads((SKILL / "evals" / "evals.json").read_text())["evals"]
    assert {e["name"] for e in evals} == set(check.CHECKS)
    for e in evals:
        fixture = SKILL / e["files"][0]
        assert (fixture / "state.json").is_file()
        run = check.Run.__new__(check.Run)
        run.before = run.after = json.loads((fixture / "state.json").read_text())
        run.reply, run.calls, run.sandbox = "", [], fixture
        graded = [text for text, _, _ in check.CHECKS[e["name"]](run)]
        assert graded == e["expectations"], e["name"]


def test_an_agent_that_does_nothing_fails_every_scenario():
    """A do-nothing run must not score full marks anywhere (no free passes)."""
    spec = importlib.util.spec_from_file_location("check", SKILL / "evals" / "check.py")
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    for name, fn in check.CHECKS.items():
        fixture = SKILL / "evals" / "files" / name
        run = check.Run.__new__(check.Run)
        run.before = run.after = json.loads((fixture / "state.json").read_text())
        run.reply, run.calls, run.sandbox = "", [], fixture
        results = [ok for _, ok, _ in fn(run)]
        assert not all(results), name
