"""Runs untrusted commands (the author's code, under test) with as little of the user's machine as possible.

Today: an allow-listed environment (no API keys, tokens or SSH agent) and a throwaway HOME. Network and
filesystem isolation are added on top of this one function, so every caller gets them at once.
"""

import os
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


def clean_env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ENV_ALLOWLIST}
    env.setdefault("PATH", os.defpath)
    # The interpreter running the squad, so its pytest is found; never the user's shell config.
    env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env['PATH']}"
    env.update(HOME=str(home), TMPDIR=str(home), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", GIT_CONFIG_NOSYSTEM="1")
    return env


def run(cmd: list[str], cwd: Path, timeout: int = 120) -> Result:
    with tempfile.TemporaryDirectory(prefix="squad-home-") as home:
        try:
            done = subprocess.run(
                cmd, cwd=cwd, env=clean_env(Path(home)), capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as err:
            out = (err.stdout or b"").decode(errors="replace") if isinstance(err.stdout, bytes) else (err.stdout or "")
            return Result(None, out + f"\n(timed out after {timeout}s)", timed_out=True)
    return Result(done.returncode, done.stdout + done.stderr)
