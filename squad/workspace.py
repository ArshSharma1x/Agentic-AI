"""The sandboxed working copy that agents read and edit through the workspace MCP server."""

import ast
import os
import shutil
import re
import subprocess
import sys
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

MAX_READ_BYTES = 100_000
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
PROTECTED_DIRS = {"tests"}
MONEY_FUNCTIONS = {"refund", "charge", "transfer", "payout"}
DANGEROUS_CALLS = re.compile(r"\b(eval|exec)\(|pickle\.loads|os\.system\(|shell\s*=\s*True")
HARDCODED_SECRET = re.compile(r"(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]", re.I)
GIT_IDENTITY = ["-c", "user.name=squad", "-c", "user.email=squad@local"]


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
            ["git", *GIT_IDENTITY, *args], cwd=self.root, capture_output=True, text=True, timeout=30
        )
        if done.returncode != 0:
            raise WorkspaceError(done.stderr.strip() or f"git {args[0]} failed")
        return done.stdout

    def init_repo(self) -> None:
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

    def read_file(self, path: str) -> str:
        target = self._resolve(path)
        if not target.is_file():
            raise WorkspaceError(f"no such file: {path}")
        if target.stat().st_size > MAX_READ_BYTES:
            raise WorkspaceError(f"file too large to read: {path}")
        return target.read_text()

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        first = target.relative_to(self.root).parts[0]
        if first in PROTECTED_DIRS:
            raise WorkspaceError(f"{first}/ is read-only: agents may not edit the tests")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content)} chars to {path}"

    def run_tests(self, timeout: int = 60) -> dict:
        try:
            done = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
                cwd=self.root, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"passed": False, "exit_code": None, "output": f"tests timed out after {timeout}s"}
        output = (done.stdout + done.stderr).strip()
        return {"passed": done.returncode == 0, "exit_code": done.returncode, "output": output[-4000:]}

    def git_diff(self) -> str:
        self._git("add", "-A")
        return self._git("diff", "--cached") or "(no changes)"

    def baseline(self) -> str:
        return self._git("rev-list", "--max-parents=0", "HEAD").split()[0]

    def changes(self) -> list[tuple[str, str]]:
        """(status, path) for everything that differs from the baseline: A added, M modified, D deleted."""
        self._git("add", "-A")
        rows = self._git("diff", "--cached", "--name-status", self.baseline()).splitlines()
        return [(row.split("\t")[0][0], row.split("\t")[-1]) for row in rows if row.strip()]

    def baseline_diff(self) -> str:
        self._git("add", "-A")
        return self._git("diff", "--cached", self.baseline()) or "(no changes)"

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
