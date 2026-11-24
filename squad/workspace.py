"""The sandboxed working copy that agents read and edit through the workspace MCP server."""

import ast
import fnmatch
import os
import shutil
import re
import subprocess
import sys
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

MAX_READ_BYTES = 100_000
READ_LINES = 2000
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
PROTECTED_DIRS = {"tests"}
MONEY_FUNCTIONS = {"refund", "charge", "transfer", "payout"}
DANGEROUS_CALLS = re.compile(r"\b(eval|exec)\(|pickle\.loads|os\.system\(|shell\s*=\s*True")
HARDCODED_SECRET = re.compile(r"(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]", re.I)
# Identity, plus overrides so a planted .git/config or hook can never run code when the orchestrator uses git.
GIT_SAFE = [
    "-c", "user.name=squad", "-c", "user.email=squad@local", "-c", "core.fsmonitor=false",
    "-c", "core.hooksPath=/dev/null", "-c", "core.sshCommand=false", "-c", "diff.external=", "-c", "core.pager=cat",
]
GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}


class WorkspaceError(ToolError):
    """An anticipated failure. As a ToolError, its message reaches the calling agent."""


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _resolve(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if path != self.root and self.root not in path.parents:
            raise WorkspaceError(f"path escapes the workspace: {relative}")
        return path

    def _git(self, *args: str) -> str:
        done = subprocess.run(
            ["git", *GIT_SAFE, *args], cwd=self.root, capture_output=True, timeout=30,
            env={**os.environ, **GIT_ENV},
        )
        if done.returncode != 0:
            raise WorkspaceError(done.stderr.decode(errors="replace").strip() or f"git {args[0]} failed")
        return done.stdout.decode(errors="replace")

    def _git_bytes(self, *args: str) -> bytes:
        done = subprocess.run(["git", *GIT_SAFE, *args], cwd=self.root, capture_output=True, timeout=30, env={**os.environ, **GIT_ENV})
        if done.returncode != 0:
            raise WorkspaceError(done.stderr.decode(errors="replace").strip() or f"git {args[0]} failed")
        return done.stdout

    def init_repo(self, ignore_caches: bool = True) -> None:
        if ignore_caches:
            ignore = self.root / ".gitignore"
            existing = ignore.read_text() if ignore.exists() else ""
            ignore.write_text(existing + ("" if existing.endswith("\n") or not existing else "\n") + "__pycache__/\n.pytest_cache/\n")
        self._git("init", "-q")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "baseline")

    def list_files(self) -> list[str]:
        return sorted(
            str(p.relative_to(self.root))
            for p in self.root.rglob("*")
            if p.is_file() and not SKIP_DIRS & set(p.relative_to(self.root).parts)
        )

    def read_file(self, path: str, offset: int = 1, limit: int = READ_LINES) -> str:
        """Numbered lines from `offset` (1-based). Says plainly when there is more, so nothing is cut silently."""
        target = self._resolve(path)
        if not target.is_file():
            raise WorkspaceError(f"no such file: {path}")
        if target.stat().st_size > MAX_READ_BYTES * 20:
            raise WorkspaceError(f"file too large to read: {path}")
        lines = target.read_text(errors="replace").splitlines()
        start = max(offset, 1) - 1
        chunk = lines[start:start + limit]
        body = "\n".join(f"{n:>5}\t{line}" for n, line in enumerate(chunk, start + 1))
        rest = len(lines) - (start + len(chunk))
        return body + (f"\n[{rest} more line(s): read_file with offset={start + len(chunk) + 1}]" if rest > 0 else "")

    def edit_file(self, path: str, old: str, new: str) -> str:
        """Replace one exact, unique occurrence of `old`. Safer than rewriting a whole file."""
        target = self._resolve(path)
        if not target.is_file():
            raise WorkspaceError(f"no such file: {path}; use write_file to create it")
        text = target.read_text()
        count = text.count(old) if old else 0
        if count != 1:
            raise WorkspaceError(f"old text found {count} times in {path}; it must match exactly once (include more context)")
        self._guard(path)
        target.write_text(text.replace(old, new, 1))
        return f"edited {path}"

    def grep(self, pattern: str, glob: str = "**/*", limit: int = 100) -> str:
        try:
            regex = re.compile(pattern)
        except re.error as err:
            raise WorkspaceError(f"bad pattern: {err}")
        hits = []
        for rel in self.glob(glob):
            try:
                for n, line in enumerate((self.root / rel).read_text().splitlines(), 1):
                    if regex.search(line):
                        hits.append(f"{rel}:{n}: {line.strip()[:200]}")
                        if len(hits) >= limit:
                            return "\n".join(hits) + f"\n[stopped at {limit} matches: narrow the pattern or glob]"
            except (UnicodeDecodeError, OSError):
                continue
        return "\n".join(hits) or "(no matches)"

    def glob(self, pattern: str) -> list[str]:
        return [f for f in self.list_files() if Path(f).match(pattern) or fnmatch.fnmatch(f, pattern)]

    def _guard(self, path: str) -> None:
        from .gate import is_ci_config, is_protected, is_test_config, norm

        rel = str(self._resolve(path).relative_to(self.root))
        if any(part.lower() == ".git" for part in Path(rel).parts):
            raise WorkspaceError("the .git directory is off limits")
        if is_test_config(rel) or is_ci_config(rel):
            raise WorkspaceError(f"{rel} controls how tests or CI run; agents may not create or change it")
        if is_protected(rel) and norm(rel) in self._baseline_protected():
            raise WorkspaceError(f"{rel} is an existing test and is read-only. Add new tests in a new file instead.")

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        self._guard(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content)} chars to {path}"

    def has_python_tests(self) -> bool:
        return any(
            p.suffix == ".py" and (p.name.startswith("test_") or p.name.endswith("_test.py"))
            for p in self.root.rglob("*.py") if not SKIP_DIRS & set(p.relative_to(self.root).parts)
        )

    def run_tests(self, timeout: int = 60) -> dict:
        """The author's own check while working. It is advisory: the gate re-runs the original tests itself."""
        from . import sandbox

        if not self.has_python_tests():
            return {"passed": None, "exit_code": None, "output": "no pytest tests in this project, so nothing was run. The gate will report this change as UNVERIFIED unless you add tests in new files."}
        result = sandbox.run(sandbox.pytest_command(self.root, "-q", "--no-header"), self.root, timeout=timeout)
        return {"passed": result.exit_code == 0, "exit_code": result.exit_code, "output": result.output.strip()[-4000:]}

    def git_diff(self) -> str:
        self._git("add", "-A")
        return self._git("diff", "--cached", "--no-ext-diff") or "(no changes)"

    def _baseline_protected(self) -> set[str]:
        from .gate import is_protected, norm

        if not hasattr(self, "_protected_cache"):
            self._protected_cache = {norm(f) for f in self.baseline_files() if is_protected(f)}
        return self._protected_cache

    def baseline_files(self) -> list[str]:
        return [f for f in self._git("ls-tree", "-r", "--name-only", self.baseline()).splitlines() if f]

    def baseline_bytes(self, path: str) -> bytes | None:
        try:
            return self._git_bytes("show", f"{self.baseline()}:{path}")
        except WorkspaceError:
            return None

    def export_baseline(self, dest: Path) -> None:
        """The project exactly as it was before any agent touched it."""
        import tarfile
        from io import BytesIO

        dest.mkdir(parents=True)
        with tarfile.open(fileobj=BytesIO(self._git_bytes("archive", self.baseline()))) as archive:
            archive.extractall(dest, filter="data")

    def added_lines(self, path: str) -> list[str]:
        self._git("add", "-A")
        diff = self._git("diff", "--cached", "--no-renames", "--no-ext-diff", self.baseline(), "--", path)
        return [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]

    def baseline(self) -> str:
        return self._git("rev-list", "--max-parents=0", "HEAD").split()[0]

    def changes(self) -> list[tuple[str, str]]:
        """(status, path) for everything that differs from the baseline: A added, M modified, D deleted."""
        self._git("add", "-A")
        rows = self._git("diff", "--cached", "--no-renames", "--name-status", self.baseline()).splitlines()
        return [(row.split("\t")[0][0], row.split("\t")[-1]) for row in rows if row.strip()]

    def baseline_diff(self) -> str:
        self._git("add", "-A")
        return self._git("diff", "--cached", "--no-ext-diff", self.baseline()) or "(no changes)"

    def baseline_file_at(self, ref: str, path: str) -> str | None:
        try:
            return self._git("show", f"{ref}:{path}")
        except WorkspaceError:
            return None

    def baseline_file(self, path: str) -> str | None:
        try:
            return self._git("show", f"{self.baseline()}:{path}")
        except WorkspaceError:
            return None

    def git_commit(self, message: str) -> str:
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)
        return self._git("rev-parse", "--short", "HEAD").strip()

    def security_scan(self) -> dict:
        """A small heuristic scanner. It is a tripwire, not a replacement for a real SAST tool."""
        findings: list[dict] = []
        for rel in self.list_files():
            if not rel.endswith(".py") or rel.split("/")[0] in PROTECTED_DIRS:
                continue
            source = (self.root / rel).read_text()
            for number, line in enumerate(source.splitlines(), start=1):
                if DANGEROUS_CALLS.search(line):
                    findings.append({"rule": "dangerous-call", "file": rel, "line": number, "detail": line.strip()})
                if HARDCODED_SECRET.search(line):
                    findings.append({"rule": "hardcoded-secret", "file": rel, "line": number, "detail": "possible secret in source"})
            findings += self._missing_authorization(rel, source)
        return {"passed": not findings, "findings": findings}

    @staticmethod
    def _missing_authorization(rel: str, source: str) -> list[dict]:
        try:
            tree = ast.parse(source)
        except SyntaxError as err:
            return [{"rule": "syntax-error", "file": rel, "line": err.lineno or 0, "detail": str(err)}]
        findings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in MONEY_FUNCTIONS:
                body = ast.get_source_segment(source, node) or ""
                has_authz = "PermissionError" in body or "authorize" in body
                is_stub = "NotImplementedError" in body
                if not has_authz and not is_stub:
                    findings.append({
                        "rule": "missing-authorization-check", "file": rel, "line": node.lineno,
                        "detail": f"{node.name}() moves money but never checks who is calling it",
                    })
        return findings


COPY_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".git", ".venv", "venv", "node_modules", "runs", "dist", "build", ".next"}
SKIP_FILES = (".env", ".env.*", "squad.config.json", "*.pem", "id_rsa*", "*.key")
MAX_COPY_MB = 300


def copy_project(source: Path, dest: Path) -> None:
    """Copy a project into a match workspace. Agents never see secrets files, and huge folders are refused."""
    total = 0
    for root, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if d not in COPY_SKIP_DIRS]
        total += sum((Path(root) / f).stat().st_size for f in files if not (Path(root) / f).is_symlink())
        if total > MAX_COPY_MB * 1024 * 1024:
            raise WorkspaceError(f"{source} is over {MAX_COPY_MB} MB: start the squad from a smaller project folder")
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(*COPY_SKIP_DIRS, *SKIP_FILES), symlinks=True)
