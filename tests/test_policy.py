"""Policy comes from the base commit, so a change can never loosen the rules that judge it."""

import json
import subprocess

import pytest

from squad import evidence
from squad.cli import main
from squad.policy import PolicyError, parse
from squad.verify import verify


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True, capture_output=True)


def make_repo(tmp_path, policy="", tests=True):
    root = tmp_path / "repo"
    (root / "payments").mkdir(parents=True)
    (root / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (root / "payments" / "refund.py").write_text("def refund():\n    return 0\n")
    if tests:
        (root / "tests").mkdir()
        (root / "tests" / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    if policy:
        (root / ".agentic.toml").write_text(policy)
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def checks(result):
    return {c.name: c for c in result.report.checks}


def test_an_agent_cannot_loosen_the_policy_in_its_own_change(tmp_path):
    repo = make_repo(tmp_path, 'sensitive = ["payments/**"]\n')
    (repo / ".agentic.toml").write_text("allow_test_changes = true\n")
    (repo / "tests" / "test_calc.py").write_text("def test_add():\n    assert True\n")
    result = verify(repo)
    assert result.policy.sensitive == ("payments/**",) and not result.policy.allow_test_changes
    assert checks(result)["integrity"].status == "FAIL" and ".agentic.toml" in checks(result)["integrity"].detail


def test_sensitive_paths_need_a_human(tmp_path):
    repo = make_repo(tmp_path, 'sensitive = ["payments/**"]\n')
    (repo / "payments" / "refund.py").write_text("def refund():\n    return 1\n")
    result = verify(repo)
    assert result.report.verdict == "UNVERIFIED" and checks(result)["policy"].data["sensitive"] == ["payments/refund.py"]


def test_require_tests_turns_unverified_into_fail(tmp_path):
    repo = make_repo(tmp_path, "require_tests = true\n", tests=False)
    (repo / "calc.py").write_text("def add(a, b):\n    return b + a\n")
    assert verify(repo).report.verdict == "FAIL"


def test_allowed_test_changes_are_reported_and_the_edited_tests_run(tmp_path):
    repo = make_repo(tmp_path, "allow_test_changes = true\n")
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b + 1\n")
    (repo / "tests" / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 6\n")
    result = verify(repo)
    assert result.report.verdict == "PASS"
    assert checks(result)["integrity"].data["test_changes_allowed_by_policy"] == ["tests/test_calc.py"]


def test_bad_policy_is_a_usage_error(tmp_path, monkeypatch):
    with pytest.raises(PolicyError):
        parse("nework = 'none'\n", "test")
    repo = make_repo(tmp_path, "network = 'everything'\n")
    (repo / "calc.py").write_text("X = 1\n")
    monkeypatch.chdir(repo)
    assert main(["verify", "-q"]) == 3


def test_evidence_is_an_in_toto_statement_bound_to_the_verified_tree(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n\n# reviewed\n")
    monkeypatch.chdir(repo)
    out, summary = tmp_path / "evidence.json", tmp_path / "summary.md"
    assert main(["verify", "-q", "--evidence", str(out), "--summary-md", str(summary), "--subject", "git+https://example/repo@abc"]) == 0
    statement = json.loads(out.read_text())
    assert statement["_type"] == evidence.STATEMENT_TYPE and statement["predicateType"] == evidence.PREDICATE_TYPE
    subject = statement["subject"][0]
    assert subject["name"] == "git+https://example/repo@abc" and len(subject["digest"]["sha256"]) == 64
    predicate = statement["predicate"]
    assert predicate["verdict"] == "PASS" and predicate["changes"][0]["path"] == "calc.py" and predicate["changes"][0]["sha256"]
    assert {c["name"] for c in predicate["checks"]} >= {"integrity", "compile", "tests"}
    assert "Agentic verify: PASS" in summary.read_text()
    # The same tree always gets the same digest, so a signature over it pins exactly what was verified.
    assert verify(repo).tree_sha256 == subject["digest"]["sha256"]
