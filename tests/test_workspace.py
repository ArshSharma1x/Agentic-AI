import pytest

from squad.workspace import Workspace, WorkspaceError


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    (tmp_path / "app.py").write_text("x = 1\n")
    workspace = Workspace(tmp_path)
    workspace.init_repo()
    return workspace


def test_paths_cannot_escape_the_workspace(ws):
    with pytest.raises(WorkspaceError, match="escapes"):
        ws.read_file("../outside.txt")
    with pytest.raises(WorkspaceError, match="escapes"):
        ws.write_file("../../evil.py", "x")


def test_tests_directory_is_read_only(ws):
    with pytest.raises(WorkspaceError, match="read-only"):
        ws.write_file("tests/test_x.py", "def test_x():\n    pass\n")


def test_write_then_diff_and_commit(ws):
    ws.write_file("app.py", "x = 2\n")
    assert "+x = 2" in ws.git_diff()
    assert ws.git_commit("change x")
    assert ws.git_diff() == "(no changes)"


def test_security_scan_flags_unchecked_money_function_and_secrets(ws):
    ws.write_file("pay.py", "def refund(user, amount):\n    return amount\n\nAPI_KEY = 'sk-1234567890abcdef'\n")
    rules = {f["rule"] for f in ws.security_scan()["findings"]}
    assert rules == {"missing-authorization-check", "hardcoded-secret"}


def test_security_scan_passes_when_authorization_is_checked(ws):
    ws.write_file("pay.py", "def refund(user, owner):\n    if user != owner:\n        raise PermissionError\n")
    assert ws.security_scan()["passed"]
