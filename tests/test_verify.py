"""`agentic verify` on a real git repo: changes made by an outside agent, gated without touching the repo."""

import os
import subprocess

import pytest

from squad.cli import main
from squad.verify import VerifyError, verify

GOOD = "def add(a, b):\n    return a + b\n"


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "calc.py").write_text(GOOD)
    (root / "tests" / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    (root / ".gitignore").write_text(".env\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def test_uncommitted_work_is_checked_against_head(repo):
    (repo / "calc.py").write_text(GOOD + "\ndef sub(a, b):\n    return a - b\n")
    result = verify(repo)
    assert result.report.verdict == "PASS" and result.base_label.startswith("HEAD")
    assert ("M", "calc.py") in result.changes


def test_a_tampering_agent_is_caught_and_the_repo_is_untouched(repo):
    (repo / "calc.py").write_text("def add(a, b):\n    return 0\n")
    (repo / "tests" / "test_calc.py").write_text("def test_add():\n    assert True\n")
    before = {p: p.read_text() for p in repo.rglob("*.py")}
    result = verify(repo)
    assert result.report.verdict == "FAIL"
    checks = {c.name: c.status for c in result.report.checks}
    assert checks["integrity"] == "FAIL" and checks["tests"] == "FAIL"
    assert {p: p.read_text() for p in repo.rglob("*.py")} == before


def test_a_branch_is_checked_against_where_it_left_main(repo):
    git(repo, "checkout", "-q", "-b", "agent/feature")
    (repo / "calc.py").write_text("def add(a, b):\n    return a * b\n")
    git(repo, "commit", "-q", "-am", "agent change")
    result = verify(repo)
    assert "main" in result.base_label and result.report.verdict == "FAIL"


def test_secrets_files_are_never_copied_into_the_check(repo):
    (repo / ".env").write_text("API_KEY=secret\n")
    (repo / "notes.py").write_text("X = 1\n")
    result = verify(repo)
    assert all(path != ".env" for _, path in result.changes)


def test_nothing_to_verify_is_an_error_not_a_pass(repo):
    with pytest.raises(VerifyError, match="nothing to verify"):
        verify(repo)


def test_cli_exit_codes_follow_the_verdict(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    (repo / "calc.py").write_text(GOOD + "\n# ok\n")
    assert main(["verify", "-q"]) == 0
    (repo / "calc.py").write_text("def add(a, b):\n    return 1\n")
    assert main(["verify", "-q", "--json", str(repo.parent / "r.json")]) == 1
    assert '"verdict": "FAIL"' in (repo.parent / "r.json").read_text()
    assert main(["verify", "--base", "no-such-ref"]) == 3


def test_a_human_can_approve_test_changes_and_the_approval_is_recorded(repo):
    (repo / "tests" / "test_old.py").write_text("def test_old():\n    assert True\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "old test")
    (repo / "tests" / "test_old.py").unlink()  # a feature removed along with its test
    (repo / "tests" / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5 and add(0, 0) == 0\n")
    assert verify(repo).report.verdict == "FAIL"
    approved = verify(repo, approve_test_changes="a maintainer")
    assert approved.report.verdict == "PASS" and "approved by a maintainer" in approved.policy.source
