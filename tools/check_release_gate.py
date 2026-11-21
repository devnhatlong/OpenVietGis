"""Fail-closed release preflight for an exact checkout.

This command never creates/approves a verification record. It detects whether
one is already available in the release inventory and refuses a release if its
candidate, scope or mandatory certification status is absent. A successful
structural preflight is not independent CI, security or human acceptance.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Any

from openvietgis_api.domains.ops.domain import (
    MANDATORY_TEAM_RELEASE,
    RELEASE_IDS,
    release_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
_SHA = re.compile(r"^[0-9a-f]{40}$")


def release_gate_failures(report: dict[str, Any], candidate: str) -> list[str]:
    """Reject absent, wrong-scope or internally inconsistent certification."""
    failures: list[str] = []
    if not _SHA.fullmatch(candidate):
        failures.append("Expected an integrity-pinned 40-character source SHA.")
    if report.get("enabled_semantics") != "release_certification":
        failures.append("Capability flags do not identify release certification.")
    if report.get("profile") != "self_host_team":
        failures.append("Only the proposed small-team self-host profile is in scope.")
    if (
        report.get("profile_status") != "accepted"
        or report.get("production_ready") is not True
    ):
        failures.append("No accepted deployment profile; readiness is withheld.")
    if report.get("verified_candidate") != candidate:
        failures.append("No verification pinned to this exact candidate.")
    if not report.get("verification_record"):
        failures.append("Independent release verification record is absent.")

    rows = report.get("items")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return [*failures, "Release inventory is missing or malformed."]

    ids = [row.get("id") for row in rows]
    if (
        len(ids) != len(RELEASE_IDS)
        or any(not isinstance(release_id, str) for release_id in ids)
        or set(ids) != RELEASE_IDS
    ):
        failures.append(
            "Release inventory must contain each stable roadmap ID exactly once."
        )
    if report.get("total_releases") != len(rows):
        failures.append("Inventory count does not match its records.")

    certified = {
        row["id"]
        for row in rows
        if isinstance(row.get("id"), str)
        and row.get("enabled") is True
        and row.get("status") == "accepted"
        and row.get("evidence")
    }
    advertised = {
        row["id"]
        for row in rows
        if isinstance(row.get("id"), str) and row.get("enabled") is True
    }
    if certified != advertised:
        failures.append("One or more advertised releases lack accepted evidence.")
    if report.get("accepted_release_count") != len(certified):
        failures.append(
            "Certification count is inconsistent with evidence-bearing records."
        )
    missing = MANDATORY_TEAM_RELEASE - certified
    if missing:
        failures.append(
            "Mandatory team releases not certified: " + ", ".join(sorted(missing))
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate", help="Exact runtime candidate SHA (default: current HEAD)"
    )
    args = parser.parse_args()
    candidate = (
        args.candidate
        or subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout.strip()
    )

    print(f"Release preflight — candidate {candidate}")
    failures = release_gate_failures(release_inventory(), candidate)
    if failures:
        for reason in failures:
            print(f"RELEASE BLOCKED: {reason}")
        return 1
    print(
        "Release inventory structurally consistent; independent acceptance still required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
