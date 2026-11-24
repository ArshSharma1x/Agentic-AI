"""Runs untrusted commands (the author's code, under test) with as little of the user's machine as possible.

Every command gets an allow-listed environment (no API keys, tokens or SSH agent) and a throwaway HOME. On top of
that, where the OS allows it:
  - macOS: Seatbelt (sandbox-exec), the mechanism Claude Code also uses;
  - Linux: bubblewrap, with a private network namespace;
which together mean no network, no reading the user's home directory (~/.ssh, ~/.aws, other projects), and no
writing outside the working directory. Where neither is available the command still runs, and the result says
isolation was "none" so the evidence never overstates what happened.
"""

import functools
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "JAVA_HOME")


@dataclass(frozen=True)
class Result:
    exit_code: int | None  # None when the command timed out
    output: str
    timed_out: bool = False
    isolation: str = "none"


def clean_env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ENV_ALLOWLIST}
    env.setdefault("PATH", os.defpath)
    # The interpreter running the squad, so its pytest is found; never the user's shell config.
    env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env['PATH']}"
    env.update(HOME=str(home), TMPDIR=str(home), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", GIT_CONFIG_NOSYSTEM="1")
    return env


def _readable_roots() -> list[Path]:
    """What the interpreter needs to start, even when it lives inside the user's home directory."""
    roots = {Path(sys.prefix), Path(sys.base_prefix), Path(sys.executable).resolve().parent}
    java = os.environ.get("JAVA_HOME")
    if java:
        roots.add(Path(java))
    return sorted(roots)


def _quote(path: Path) -> str:
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _seatbelt_profile(writable: list[Path]) -> str:
    home = Path.home().resolve()
    reads = "\n".join(f"  (subpath {_quote(p)})" for p in [*_readable_roots(), *writable])
    writes = "\n".join(f"  (subpath {_quote(p)})" for p in writable)
    return f"""(version 1)
(allow default)
(deny network*)
(allow network* (local unix))
(deny file-read* (subpath {_quote(home)}))
(allow file-read-metadata)
(allow file-read*
{reads})
(deny file-write*)
(allow file-write*
{writes}
  (literal "/dev/null") (literal "/dev/zero") (literal "/dev/tty") (regex #"^/dev/fd/"))
"""


@functools.cache
def isolation() -> str:
    """The strongest isolation this machine supports: seatbelt, bubblewrap, or none."""
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        return "seatbelt"
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        probe = subprocess.run(
            ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--unshare-net", "--", "true"], capture_output=True, timeout=10
        )
        if probe.returncode == 0:
            return "bubblewrap"
    return "none"


def _wrap(cmd: list[str], writable: list[Path]) -> list[str]:
    kind = isolation()
    if kind == "seatbelt":
        return ["sandbox-exec", "-p", _seatbelt_profile(writable), *cmd]
    if kind == "bubblewrap":
        args = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp"]
        for hidden in ("/home", "/root", "/Users"):
            if Path(hidden).is_dir():
                args += ["--tmpfs", hidden]
        for root in _readable_roots():
            args += ["--ro-bind", str(root), str(root)]
        for path in writable:
            args += ["--bind", str(path), str(path)]
        return [*args, "--unshare-net", "--unshare-pid", "--die-with-parent", "--new-session", "--", *cmd]
    return cmd


def run(cmd: list[str], cwd: Path, timeout: int = 120, writable: tuple[Path, ...] = ()) -> Result:
    """Run `cmd` in `cwd`. Only `cwd`, the throwaway HOME and `writable` can be written to."""
    with tempfile.TemporaryDirectory(prefix="squad-home-") as home:
        home = Path(home).resolve()
        allowed = [Path(cwd).resolve(), home, *(Path(p).resolve() for p in writable)]
        try:
            done = subprocess.run(
                _wrap(cmd, allowed), cwd=cwd, env=clean_env(home), capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as err:
            out = err.stdout.decode(errors="replace") if isinstance(err.stdout, bytes) else (err.stdout or "")
            return Result(None, out + f"\n(timed out after {timeout}s)", timed_out=True, isolation=isolation())
    return Result(done.returncode, done.stdout + done.stderr, isolation=isolation())


def pytest_command(root: Path, *extra: str) -> list[str]:
    """pytest pinned to `root`: it must not walk up into parent folders for config, which the sandbox hides anyway."""
    root = Path(root).resolve()
    return [sys.executable, "-m", "pytest", f"--rootdir={root}", f"--confcutdir={root}", "-c", str(_pytest_config(root)), "-p", "no:cacheprovider", *extra, str(root)]


def _pytest_config(root: Path) -> Path:
    """The project's own pytest config, found the way pytest finds it but only inside the project root."""
    import configparser
    import tomllib

    for name in ("pytest.ini", ".pytest.ini"):
        if (root / name).is_file():
            return root / name
    try:
        if (root / "pyproject.toml").is_file() and "pytest" in tomllib.loads((root / "pyproject.toml").read_text()).get("tool", {}):
            return root / "pyproject.toml"
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        pass
    for name, section in (("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")):
        parser = configparser.ConfigParser(interpolation=None)
        try:
            if (root / name).is_file() and parser.read(root / name) and parser.has_section(section):
                return root / name
        except configparser.Error:
            pass
    return Path(os.devnull)  # no config: an empty one, rather than whatever sits in a parent folder
