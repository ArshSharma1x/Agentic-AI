"""The evidence a verification leaves behind: an in-toto Statement anyone can check without trusting the agent.

Locally the statement is written unsigned. In CI the GitHub Action signs it with GitHub artifact attestations
(Sigstore, keyless), so `gh attestation verify` can prove which workflow produced it and that it was not edited.
"""

import datetime
import json
from importlib.metadata import PackageNotFoundError, version

from .verify import Verification

PREDICATE_TYPE = "https://github.com/ArshSharma1x/Agentic-AI/attestations/verification/v0.1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"


def _version() -> str:
    try:
        return version("agentic-squad")
    except PackageNotFoundError:
        return "unknown"


def predicate(result: Verification) -> dict:
    report = result.report.to_dict()
    return {
        "verifier": {"id": "https://github.com/ArshSharma1x/Agentic-AI", "version": _version()},
        "verifiedAt": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "base": {"commit": result.base, "label": result.base_label},
        "head": result.head_label,
        "verdict": report["verdict"],
        "isolation": report["isolation"],
        "policy": result.policy.to_dict(),
        "changes": result.to_dict()["changes"],
        "checks": report["checks"],
    }


def statement(result: Verification, subject_name: str) -> dict:
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": subject_name, "digest": {"sha256": result.tree_sha256}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": predicate(result),
    }


def summary_markdown(result: Verification) -> str:
    """A table for a CI job summary or a PR comment."""
    report = result.report
    icon = {"PASS": "✅", "FAIL": "❌", "UNVERIFIED": "⚠️"}
    rows = "\n".join(f"| {icon[c.status]} {c.status} | {c.name} | {c.detail.replace('|', '/')} |" for c in report.checks)
    return (
        f"## {icon[report.verdict]} Agentic verify: {report.verdict}\n\n"
        f"{len(result.changes)} file(s) changed against `{result.base[:10]}` ({result.base_label}). "
        f"Sandbox: `{report.isolation}`. Policy: {result.policy.source}.\n\n"
        f"| Result | Check | Detail |\n|---|---|---|\n{rows}\n\n"
        f"Tree digest `sha256:{result.tree_sha256}`\n"
    )


def write(path, data) -> None:
    with open(path, "w") as out:
        json.dump(data, out, indent=2)
