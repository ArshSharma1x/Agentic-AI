"""`agentic verify`: gate a change made by any agent (Claude Code, Codex, Cursor, a person) in any git repo.

It rebuilds the change in a private working copy, with the base commit as the baseline, and runs WARDEN on it.
Nothing in the user's repo is modified, and the repo's own git hooks and config never run.
"""

import dataclasses
import fnmatch
import shutil
import tarfile
import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import hashlib

from .gate import Gate, GateReport
from .policy import POLICY_FILE, Policy, parse
from .workspace import SKIP_FILES, Workspace, WorkspaceError

BASE_CANDIDATES = ("origin/HEAD", "origin/main", "main", "origin/master", "master")


class VerifyError(Exception):
    pass


@dataclass
class Verification:
    repo: str
    base: str
    base_label: str
    head_label: str
    changes: list[tuple[str, str]] = field(default_factory=list)
    report: GateReport | None = None
    policy: Policy = field(default_factory=Policy)
    file_digests: dict[str, str] = field(default_factory=dict)  # sha256 of every changed file as verified
    tree_sha256: str = ""  # one digest over every file in the verified tree: the attestation's subject

    def to_dict(self) -> dict:
        return {
            "repo": self.repo, "base": self.base, "base_label": self.base_label, "head": self.head_label,
            "tree_sha256": self.tree_sha256, "policy": self.policy.to_dict(),
            "changes": [{"status": s, "path": p, "sha256": self.file_digests.get(p)} for s, p in self.changes],
            **(self.report.to_dict() if self.report else {}),
        }


def _git(repo: Path, *args: str) -> str:
    return Workspace(repo)._git(*args).strip()


def _has(repo: Path, ref: str) -> bool:
    try:
        _git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
        return True
    except WorkspaceError:
        return False


def resolve(repo: Path, base: str | None, head: str | None) -> tuple[str, str, str]:
    """(base sha, base label, head label). With no --base: uncommitted work is checked against HEAD;
    otherwise the branch is checked against where it left main."""
    try:
        _git(repo, "rev-parse", "--git-dir")
    except WorkspaceError:
        raise VerifyError(f"{repo} is not a git repository")
    head_label = head or "your working tree"
    if base:
        if not _has(repo, base):
            raise VerifyError(f"unknown base: {base}")
        return _git(repo, "rev-parse", f"{base}^{{commit}}"), base, head_label
    if head is None and _git(repo, "status", "--porcelain", "--untracked-files=normal"):
        return _git(repo, "rev-parse", "HEAD"), "HEAD (uncommitted changes)", head_label
    tip = _git(repo, "rev-parse", head or "HEAD")
    for candidate in BASE_CANDIDATES:
        if _has(repo, candidate):
            fork = _git(repo, "merge-base", tip, candidate)
            if fork != tip:
                return fork, f"where this branch left {candidate}", head_label if head else "HEAD"
    raise VerifyError("nothing to verify: no uncommitted changes and HEAD is not ahead of main. Pass --base <ref>.")


def _extract(repo: Path, ref: str, dest: Path) -> None:
    with tarfile.open(fileobj=BytesIO(Workspace(repo)._git_bytes("archive", ref))) as archive:
        archive.extractall(dest, filter="data")


def _secret(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(name, pattern) for pattern in SKIP_FILES)


def build(repo: Path, base: str, head: str | None, dest: Path) -> Path:
    """A private working copy: the base commit as the baseline, the change on top."""
    ws = dest / "workspace"
    ws.mkdir(parents=True)
    _extract(repo, base, ws)
    Workspace(ws).init_repo(ignore_caches=False)
    for child in ws.iterdir():
        if child.name != ".git":
            shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
    if head:
        _extract(repo, head, ws)
        return ws
    listed = _git(repo, "ls-files", "-co", "--exclude-standard").splitlines()
    for rel in listed:
        source = repo / rel
        if _secret(rel) or not (source.is_file() or source.is_symlink()):
            continue  # deleted in the working tree, or a secrets file the gate never needs
        target = ws / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
    return ws


def _digests(ws: Path, changes: list[tuple[str, str]]) -> tuple[dict[str, str], str]:
    files = sorted(p for p in ws.rglob("*") if p.is_file() and ".git" not in p.relative_to(ws).parts)
    tree = hashlib.sha256()
    for path in files:
        tree.update(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ws).as_posix()}\n".encode())
    changed = {rel: hashlib.sha256((ws / rel).read_bytes()).hexdigest() for status, rel in changes if status != "D" and (ws / rel).is_file()}
    return changed, tree.hexdigest()


def verify(
    repo: Path, *, base: str | None = None, head: str | None = None, hidden: Path | None = None, network: str | None = None,
    approve_test_changes: str | None = None,
) -> Verification:
    repo = Path(repo).resolve()
    sha, base_label, head_label = resolve(repo, base, head)
    # The rules come from the base commit: the change being judged cannot rewrite them.
    policy = parse(Workspace(repo).baseline_file_at(sha, POLICY_FILE), f"{POLICY_FILE} at {sha[:10]}")
    if approve_test_changes:
        # A human said yes to this change's test edits (e.g. a maintainer's PR label). It is recorded, not implied.
        policy = dataclasses.replace(policy, allow_test_changes=True, source=f"{policy.source}; test changes approved by {approve_test_changes}")
    result = Verification(str(repo), sha, base_label, head_label, policy=policy)
    with tempfile.TemporaryDirectory(prefix="agentic-verify-") as scratch:
        ws = build(repo, sha, head, Path(scratch))
        result.changes = Workspace(ws).changes()
        result.file_digests, result.tree_sha256 = _digests(ws, result.changes)
        result.report = Gate(ws, hidden_tests=hidden.resolve() if hidden else None, policy=policy, network=network).run()
    return result
