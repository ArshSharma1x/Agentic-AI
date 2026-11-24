"""WARDEN, the deterministic gate. It decides from facts (exit codes, per-test results, hashes), never from a model.

Given a workspace with a git baseline, the gate:
  1. checks integrity: the author may add tests but may not change, move or delete existing ones, touch test
     configuration or CI, or make source code detect that it is running under test;
  2. compiles what changed;
  3. runs the ORIGINAL tests (test files and config restored from the baseline, so tampering cannot change the
     result) plus any hidden tests the author never saw, and compares per-test outcomes with the baseline, so
     only failures the change introduced count against it.

Verdicts: PASS, FAIL, or UNVERIFIED (nothing could prove the change works, e.g. there are no tests).
"""

import ast
import configparser
import hashlib
import json
import re
import shutil
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import sandbox
from .policy import POLICY_FILE, Policy
from .workspace import Workspace

PASS, FAIL, UNVERIFIED = "PASS", "FAIL", "UNVERIFIED"
TEST_CONFIG_NAMES = {"conftest.py", "pytest.ini", "tox.ini", "noxfile.py", "sitecustomize.py", "usercustomize.py", ".coveragerc"}
CI_PREFIXES = (".github/workflows/", ".gitlab-ci.yml", ".circleci/", "jenkinsfile", "azure-pipelines.yml", ".buildkite/")
# Source code that changes behaviour under test, or ends the process early with a success code.
UNDER_TEST = re.compile(r"PYTEST_CURRENT_TEST|['\"]pytest['\"]\s+in\s+sys\.modules|sys\.modules\s*\[\s*['\"]pytest|\bos\._exit\s*\(")
HIDDEN_DIR = "_squad_hidden_tests"
NO_CHECKER = {".ts", ".tsx", ".go", ".rs", ".rb", ".c", ".cc", ".cpp", ".h", ".cs", ".kt", ".swift", ".scala", ".php"}


def norm(rel: str) -> str:
    """Paths compared the way a case-insensitive filesystem sees them."""
    return rel.replace("\\", "/").lower()


def is_test_file(rel: str) -> bool:
    parts = norm(rel).split("/")
    name = parts[-1]
    return name.endswith(".py") and (
        name.startswith("test_") or name.endswith("_test.py") or any(p in ("tests", "test") for p in parts[:-1])
    )


def is_test_config(rel: str) -> bool:
    name = norm(rel).split("/")[-1]
    return name in TEST_CONFIG_NAMES or name.endswith(".pth")


def is_ci_config(rel: str) -> bool:
    """CI and the gate's own policy: an author must never edit what decides whether its work ships."""
    return norm(rel).startswith(CI_PREFIXES) or norm(rel) == POLICY_FILE


def is_protected(rel: str) -> bool:
    return is_test_file(rel) or is_test_config(rel) or is_ci_config(rel)


def test_file_edit(before: str | None, after: str | None) -> tuple[bool, str, list[str]]:
    """(only additions?, reason if not, names of added tests) for an edited Python test file.

    Appending new tests is welcome. Every original statement must survive unchanged (compared as syntax trees),
    and the only new top-level code allowed is new test functions or classes and imports: no skip markers,
    `pytestmark`, fixtures, or a second definition that silently replaces an original test.
    """
    if before is None or after is None:
        return False, "deleted", []
    try:
        old, new = ast.parse(before), ast.parse(after)
    except SyntaxError:
        return False, "no longer parses", []
    old_dumps = [ast.dump(n) for n in old.body]
    new_dumps = [ast.dump(n) for n in new.body]
    remaining = list(new_dumps)
    for dump in old_dumps:
        if dump not in remaining:
            return False, "an original test or statement was changed or removed", []
        remaining.remove(dump)
    original_names = {getattr(n, "name", None) for n in old.body} - {None}
    added = []
    for node, dump in zip(new.body, new_dumps):
        if dump in old_dumps:
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        name = getattr(node, "name", "")
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False, "new module-level code (it could change how the original tests run)", []
        if name in original_names:
            return False, f"redefines the original {name}", []
        if not (name.startswith("test") or name.startswith("Test")):
            return False, f"adds {name}, which is not a test (fixtures and helpers can change how the originals run)", []
        if any(not _is_parametrize(d) for d in node.decorator_list):
            return False, f"decorates the new {name} with something other than parametrize", []
        added.append(name)
    return True, "", added


def _is_parametrize(decorator: ast.AST) -> bool:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    return isinstance(target, ast.Attribute) and target.attr == "parametrize"


def _pytest_section(name: str, text: str | None):
    """The part of a shared config file that changes how pytest behaves."""
    if text is None:
        return None
    try:
        if name == "pyproject.toml":
            return tomllib.loads(text).get("tool", {}).get("pytest")
        if name == "setup.cfg":
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(text)
            return dict(parser["tool:pytest"]) if parser.has_section("tool:pytest") else None
    except (tomllib.TOMLDecodeError, configparser.Error):
        return "<unparseable>"
    return None


@dataclass
class Check:
    name: str
    status: str
    detail: str
    data: dict = field(default_factory=dict)


@dataclass
class GateReport:
    checks: list[Check]
    isolation: str = field(default_factory=sandbox.isolation)  # how the author's code was contained while it ran

    @property
    def verdict(self) -> str:
        statuses = {c.status for c in self.checks}
        return FAIL if FAIL in statuses else UNVERIFIED if UNVERIFIED in statuses else PASS

    @property
    def issues(self) -> list[str]:
        """What the author is told. Hidden-test details stay out, so the author cannot fit to them."""
        return [f"{c.name}: {c.detail}" for c in self.checks if c.status == FAIL]

    @property
    def unverified(self) -> list[str]:
        return [f"{c.name}: {c.detail}" for c in self.checks if c.status == UNVERIFIED]

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "isolation": self.isolation, "checks": [asdict(c) for c in self.checks]}


@dataclass(frozen=True)
class TestRun:
    outcomes: dict[str, str]  # test id -> passed, failed, error or skipped
    exit_code: int | None
    output: str
    reported: bool  # False when pytest wrote no report (crashed, exited early, timed out)

    def ids(self, *outcomes: str) -> set[str]:
        return {t for t, o in self.outcomes.items() if o in outcomes}


class Gate:
    def __init__(self, workspace: Path, *, hidden_tests: Path | None = None, policy: Policy | None = None, network: str | None = None) -> None:
        self.ws = Workspace(workspace)
        self.hidden_tests = hidden_tests
        self.policy = policy or Policy()
        self.timeout = self.policy.timeout
        self.network = network or self.policy.network
        self._baseline_run: TestRun | None = None

    def run(self) -> GateReport:
        changes = self.ws.changes()
        checks = [self._integrity(changes), self._special_casing(changes), self._compile(changes), *self._tests(changes)]
        if self.policy.require_tests:
            checks = [Check(c.name, FAIL, c.detail + " (policy requires tests)", c.data) if c.name == "tests" and c.status == UNVERIFIED else c for c in checks]
        integrity = checks[0]
        if review := integrity.data.get("ci_or_policy_changes"):
            checks.append(Check("review", UNVERIFIED, f"changes CI or gate policy ({', '.join(review[:5])}): a human must review", {"paths": review}))
        if touched := self.policy.touches_sensitive([rel for _, rel in changes]):
            checks.append(Check("policy", UNVERIFIED, f"changes sensitive paths ({', '.join(touched[:5])}): a human must review", {"sensitive": touched}))
        return GateReport(checks)

    # 1. Integrity ------------------------------------------------------------------------------

    def _integrity(self, changes: list[tuple[str, str]]) -> Check:
        problems, added_tests, approved, review = [], [], [], []
        for status, rel in changes:
            name = norm(rel).split("/")[-1]
            if is_test_config(rel):
                problems.append(f"{'added' if status == 'A' else 'changed' if status == 'M' else 'deleted'} test configuration {rel}")
            elif name in ("pyproject.toml", "setup.cfg") and _pytest_section(name, self.ws.baseline_file(rel)) != _pytest_section(name, self._current(rel)):
                problems.append(f"changed the pytest settings in {rel}")
            elif is_ci_config(rel):
                review.append(rel)  # often legitimate, but what decides whether code ships needs human eyes
            elif is_test_file(rel):
                if status == "A":
                    added_tests.append(rel)
                elif self.policy.allow_test_changes:
                    approved.append(rel)
                elif status == "M" and (verdict := test_file_edit(self.ws.baseline_file(rel), self._current(rel)))[0]:
                    added_tests += [f"{rel}::{name}" for name in verdict[2]]  # new tests appended to an existing file
                elif status == "D":
                    problems.append(f"deleted existing test {rel}")
                else:
                    problems.append(f"changed existing test {rel} ({test_file_edit(self.ws.baseline_file(rel), self._current(rel))[1]})")
            elif rel.endswith(".py") and status != "D":
                hits = [l for l in self.ws.added_lines(rel) if UNDER_TEST.search(l)]
                if hits:
                    problems.append(f"{rel} checks whether it is running under test or exits early: {hits[0].strip()[:80]}")
        data = {"added_tests": added_tests, "problems": problems, "test_changes_allowed_by_policy": approved, "ci_or_policy_changes": review}
        if problems:
            return Check("integrity", FAIL, "; ".join(problems), data)
        note = f" ({len(added_tests)} new test file(s) added)" if added_tests else ""
        if approved:
            note += f"; {len(approved)} existing test(s) changed, allowed by policy: {', '.join(approved[:5])}"
        return Check("integrity", PASS, f"no existing tests or test configuration changed{note}", data)

    def _special_casing(self, changes: list[tuple[str, str]]) -> Check:
        """Source the change added that answers a test's exact inputs with its exact expected output."""
        from .hardcoding import expectations, find

        sources = [rel for status, rel in changes if status != "D" and rel.endswith(".py") and not is_test_file(rel)]
        if not sources:
            return Check("special-casing", PASS, "no source changes to check")
        tests = [self.ws.baseline_file(f) or "" for f in self.ws.baseline_files() if is_test_file(f)]
        wanted = expectations(tests)
        hits = [h for rel in sources for h in find(self._current(rel) or "", rel, wanted, self.ws.added_line_numbers(rel))]
        if hits:
            return Check("special-casing", UNVERIFIED, "; ".join(h.describe() for h in hits[:3]) + ": a human should check this is not fitting the tests",
                         {"hits": [h.describe() for h in hits]})
        return Check("special-casing", PASS, f"no branch special-cases a test's inputs ({len(wanted)} assertion(s) checked)")

    def _current(self, rel: str) -> str | None:
        path = self.ws.root / rel
        return path.read_text(errors="replace") if path.is_file() else None

    # 2. Compile --------------------------------------------------------------------------------

    def _compile(self, changes: list[tuple[str, str]]) -> Check:
        changed = [rel for status, rel in changes if status != "D" and (self.ws.root / rel).is_file()]
        errors, checked, unchecked = [], 0, sorted({Path(r).suffix for r in changed if Path(r).suffix in NO_CHECKER})
        for rel in changed:
            suffix = Path(rel).suffix
            if suffix == ".py":
                checked += 1
                try:
                    compile((self.ws.root / rel).read_bytes(), rel, "exec")  # parses only; nothing runs
                except (SyntaxError, ValueError) as err:
                    errors.append(f"{rel}: {err}")
            elif suffix == ".json":
                checked += 1
                try:
                    json.loads((self.ws.root / rel).read_text())
                except ValueError as err:
                    errors.append(f"{rel}: invalid JSON ({err})")
            elif suffix in (".js", ".mjs", ".cjs") and shutil.which("node"):
                checked += 1
                result = sandbox.run(["node", "--check", rel], self.ws.root, timeout=30)
                if result.exit_code != 0:
                    errors.append(f"{rel}: {result.output.strip()[:200]}")
        java = [r for r in changed if r.endswith(".java")]
        if java:
            if shutil.which("javac"):
                checked += len(java)
                with tempfile.TemporaryDirectory() as out:
                    result = sandbox.run(["javac", "-d", out, *java], self.ws.root, timeout=120, writable=(Path(out),))
                if result.exit_code != 0:
                    errors.append(f"javac: {result.output.strip()[:300]}")
            else:
                unchecked.append(".java (javac not installed)")
        if errors:
            return Check("compile", FAIL, "; ".join(errors), {"checked": checked})
        if unchecked:
            return Check("compile", UNVERIFIED, f"no checker for {', '.join(unchecked)}", {"checked": checked})
        return Check("compile", PASS, f"{checked} changed file(s) compile" if checked else "nothing to compile", {"checked": checked})

    # 3. Tests ----------------------------------------------------------------------------------

    def _tests(self, changes: list[tuple[str, str]]) -> list[Check]:
        baseline_files = self.ws.baseline_files()
        visible = [f for f in baseline_files if is_test_file(f)] + [r for s, r in changes if s == "A" and is_test_file(r)]
        hidden = sorted(p for p in self.hidden_tests.rglob("*.py")) if self.hidden_tests else []
        if not visible and not hidden:
            return [Check("tests", UNVERIFIED, "the project has no tests, so nothing proves this change works")]
        with tempfile.TemporaryDirectory(prefix="squad-gate-") as scratch:
            scratch = Path(scratch)
            pristine = self._pristine(scratch / "pristine", changes)
            with ThreadPoolExecutor(2) as pool:  # the two runs are independent
                before = pool.submit(self._baseline, scratch / "baseline") if any(is_test_file(f) for f in baseline_files) else None
                now = self._pytest(pristine)
                baseline = before.result() if before else None
            hashes = {f: _sha256(scratch / "pristine" / f) for f in sorted(visible) if (scratch / "pristine" / f).is_file()}
        checks = [self._judge(now, baseline, hashes)]
        if hidden:
            checks.append(self._judge_hidden(now))
        return checks

    def _baseline(self, dest: Path) -> TestRun:
        if self._baseline_run is None:
            self.ws.export_baseline(dest)
            self._baseline_run = self._pytest(dest)
        return self._baseline_run

    def _pristine(self, dest: Path, changes: list[tuple[str, str]]) -> Path:
        """The author's code with every protected file put back exactly as it was at the baseline."""
        shutil.copytree(self.ws.root, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"), symlinks=True)
        for status, rel in changes:
            if not self._must_restore(status, rel):
                continue
            target, original = dest / rel, self.ws.baseline_bytes(rel)
            if original is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original)
        if self.hidden_tests:
            shutil.copytree(self.hidden_tests, dest / HIDDEN_DIR)
        return dest

    def _must_restore(self, status: str, rel: str) -> bool:
        if is_test_config(rel) or is_ci_config(rel):
            return True
        if is_test_file(rel) and status != "A":
            if self.policy.allow_test_changes:
                return False
            # Run a file that only gained tests as written, so the new tests count; restore anything else.
            return not (status == "M" and test_file_edit(self.ws.baseline_file(rel), self._current(rel))[0])
        name = norm(rel).split("/")[-1]
        return name in ("pyproject.toml", "setup.cfg") and _pytest_section(name, self.ws.baseline_file(rel)) != _pytest_section(name, self._current(rel))

    def _pytest(self, root: Path) -> TestRun:
        report = root / ".squad-junit.xml"
        cmd = sandbox.pytest_command(root, "-q", f"--junitxml={report}", "-o", "junit_family=xunit2")
        result = sandbox.run(cmd, root, timeout=self.timeout, network=self.network)
        if not report.is_file():
            return TestRun({}, result.exit_code, result.output[-3000:], reported=False)
        outcomes: dict[str, str] = {}
        for case in ET.parse(report).getroot().iter("testcase"):
            test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
            kinds = {child.tag for child in case}
            outcomes[test_id] = "failed" if "failure" in kinds else "error" if "error" in kinds else "skipped" if "skipped" in kinds else "passed"
        return TestRun(outcomes, result.exit_code, result.output[-3000:], reported=True)

    @staticmethod
    def _visible(ids: set[str]) -> set[str]:
        return {t for t in ids if HIDDEN_DIR not in t}

    def _judge(self, now: TestRun, baseline: TestRun | None, hashes: dict) -> Check:
        data = {"exit_code": now.exit_code, "test_files_sha256": hashes, "output_tail": now.output[-1500:]}
        if not now.reported and baseline is not None and not baseline.reported:
            return Check("tests", UNVERIFIED, "the test suite does not complete in the sandbox even before the change "
                         f"(exit code {now.exit_code}); it may need network or services the sandbox blocks", data)
        if not now.reported:
            return Check("tests", FAIL, f"the test run produced no report (exit code {now.exit_code}); it crashed, timed out or exited early", data)
        ran = self._visible(now.ids("passed", "failed", "error"))
        failing = self._visible(now.ids("failed", "error"))
        skipped = self._visible(now.ids("skipped"))
        before_fail = baseline.ids("failed", "error") if baseline else set()
        before_pass = baseline.ids("passed") if baseline else set()
        new_failures = sorted(failing - before_fail)
        vanished = sorted(before_pass - set(now.outcomes))
        newly_skipped = sorted(before_pass & skipped)
        data.update(ran=len(ran), failed=len(failing), skipped=len(skipped), preexisting_failures=len(failing & before_fail),
                    new_failures=new_failures, vanished=vanished, newly_skipped=newly_skipped)
        problems = []
        if not ran:
            problems.append(f"no test actually ran ({len(skipped)} skipped)")
        if new_failures:
            problems.append(f"{len(new_failures)} test(s) fail: {', '.join(new_failures[:5])}")
        if vanished:
            problems.append(f"{len(vanished)} test(s) that passed before no longer run: {', '.join(vanished[:5])}")
        if newly_skipped:
            problems.append(f"{len(newly_skipped)} test(s) that passed before are now skipped: {', '.join(newly_skipped[:5])}")
        if now.exit_code not in (0, 1):
            problems.append(f"pytest exited with code {now.exit_code} (interrupted or misconfigured)")
        still = sorted(failing & before_fail)
        fixed = sorted(before_fail - failing)
        data.update(still_failing=still, fixed=fixed)
        if problems:
            return Check("tests", FAIL, "; ".join(problems), data)
        fixed_note = f", {len(fixed)} fixed" if fixed else ""
        if still and not self.policy.allow_preexisting_failures:
            # Not a regression, but not proof either: the change may simply not do what was asked.
            return Check("tests", UNVERIFIED, f"{len(still)} test(s) that failed before still fail: {', '.join(still[:5])}{fixed_note}", data)
        pre = f"; {len(still)} known failure(s) allowed by policy" if still else ""
        return Check("tests", PASS, f"{len(ran)} original test(s) ran, none newly failing{fixed_note}{pre}", data)

    @staticmethod
    def _judge_hidden(now: TestRun) -> Check:
        hidden = {t: o for t, o in now.outcomes.items() if HIDDEN_DIR in t}
        ran = [t for t, o in hidden.items() if o != "skipped"]
        failing = sorted(t for t, o in hidden.items() if o in ("failed", "error"))
        data = {"ran": len(ran), "failed": failing}  # names go to the evidence, not to the author
        if not ran:
            return Check("hidden-tests", FAIL, "none of the hidden tests ran", data)
        if failing:
            return Check("hidden-tests", FAIL, f"{len(failing)} of {len(ran)} hidden test(s) fail", data)
        return Check("hidden-tests", PASS, f"{len(ran)} hidden test(s) pass", data)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
