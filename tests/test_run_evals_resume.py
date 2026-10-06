"""An interrupted eval batch must pick up where it stopped instead of paying for finished runs again."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run_evals.py")
run_evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_evals)

EVAL = json.loads((ROOT / "skills" / "todo-list" / "evals" / "evals.json").read_text())["evals"][0]


class Called(Exception):
    pass


@pytest.fixture
def no_agent(monkeypatch):
    def boom(cmd, *args, **kwargs):
        raise Called(cmd[0])
    monkeypatch.setattr(run_evals.subprocess, "run", boom)


def test_a_finished_run_is_skipped_without_calling_the_agent(tmp_path, no_agent):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / run_evals.DONE).write_text("")
    (run_dir / "keep.txt").write_text("results from the first attempt")
    line = run_evals.run_one("todo-list", EVAL, "with_skill", run_dir, None)
    assert "already done" in line
    assert (run_dir / "keep.txt").read_text() == "results from the first attempt"


def test_a_half_finished_run_is_redone_from_scratch(tmp_path, no_agent):
    run_dir = tmp_path / "eval-x" / "with_skill" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "stale.txt").write_text("left over from the attempt that died")
    with pytest.raises(Called):
        run_evals.run_one("todo-list", EVAL, "with_skill", run_dir, None)
    assert not (run_dir / "stale.txt").exists()


def test_force_redoes_a_finished_run(tmp_path, no_agent):
    run_dir = tmp_path / "eval-x" / "with_skill" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / run_evals.DONE).write_text("")
    with pytest.raises(Called):
        run_evals.run_one("todo-list", EVAL, "with_skill", run_dir, None, force=True)
