"""The author's code runs contained: no network, no secrets, no reading or writing the user's files."""

import os
import socket
import sys
import threading
from pathlib import Path

import pytest

from squad import sandbox

isolated = pytest.mark.skipif(sandbox.isolation() == "none", reason="no OS sandbox on this machine")


def run(tmp_path, code):
    (tmp_path / "probe.py").write_text(code)
    return sandbox.run([sys.executable, "probe.py"], tmp_path, timeout=30)


def test_ci_really_runs_the_sandbox():
    if os.environ.get("CI"):
        assert sandbox.isolation() != "none", "CI must exercise the real sandbox, not skip it"


def test_secrets_in_the_environment_never_reach_the_code(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
    result = run(tmp_path, "import os\nprint(sorted(k for k in os.environ if 'KEY' in k or 'TOKEN' in k))\n")
    assert result.output.strip() == "[]"


@isolated
def test_no_network_even_to_localhost(tmp_path):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    threading.Thread(target=lambda: server.accept(), daemon=True).start()
    port = server.getsockname()[1]
    result = run(tmp_path, f"import socket\ntry:\n    socket.create_connection(('127.0.0.1', {port}), timeout=3)\n    print('CONNECTED')\nexcept OSError:\n    print('BLOCKED')\n")
    server.close()
    assert "BLOCKED" in result.output


@isolated
def test_the_users_home_directory_is_unreadable(tmp_path):
    secret = Path.home() / f".squad-sandbox-test-{os.getpid()}"
    secret.write_text("private")
    try:
        result = run(tmp_path, f"try:\n    print(open({str(secret)!r}).read())\nexcept OSError:\n    print('BLOCKED')\n")
    finally:
        secret.unlink()
    assert "private" not in result.output and "BLOCKED" in result.output


@isolated
def test_writes_outside_the_working_directory_do_not_land(tmp_path):
    work, outside = tmp_path / "work", tmp_path / "outside"
    work.mkdir()
    outside.mkdir()
    result = run(work, f"try:\n    open({str(outside / 'escaped.txt')!r}, 'w').write('x')\nexcept OSError:\n    pass\nopen('inside.txt', 'w').write('ok')\n")
    assert not (outside / "escaped.txt").exists() and (work / "inside.txt").read_text() == "ok", result.output


@isolated
def test_loopback_mode_allows_localhost_only(tmp_path):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    threading.Thread(target=lambda: server.accept(), daemon=True).start()
    port = server.getsockname()[1]
    (tmp_path / "probe.py").write_text(
        "import socket, sys\nhost = sys.argv[1]\ntry:\n    socket.create_connection((host, int(sys.argv[2])), timeout=3)\n"
        "    print('CONNECTED')\nexcept OSError:\n    print('BLOCKED')\n"
    )
    if sandbox.isolation() == "seatbelt":  # bubblewrap gives each run its own private loopback instead
        local = sandbox.run([sys.executable, "probe.py", "127.0.0.1", str(port)], tmp_path, network="loopback")
        assert "CONNECTED" in local.output
    outside = sandbox.run([sys.executable, "probe.py", "1.1.1.1", "53"], tmp_path, network="loopback")
    server.close()
    assert "BLOCKED" in outside.output
