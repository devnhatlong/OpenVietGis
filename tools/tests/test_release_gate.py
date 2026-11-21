from copy import deepcopy

from openvietgis_api.domains.ops.domain import release_inventory

from tools.check_release_gate import release_gate_failures

CANDIDATE = "1" * 40


def test_absent_exact_candidate_acceptance_blocks_release() -> None:
    reasons = release_gate_failures(release_inventory(), CANDIDATE)
    assert any("No accepted deployment profile" in reason for reason in reasons)
    assert any("exact candidate" in reason for reason in reasons)
    assert any("Mandatory team releases not certified" in reason for reason in reasons)


def test_static_all_true_flags_do_not_pass_release_gate() -> None:
    report = deepcopy(release_inventory())
    report["accepted_release_count"] = 15
    for row in report["items"]:
        row["enabled"] = True
        row["status"] = "accepted"
    reasons = release_gate_failures(report, CANDIDATE)
    assert any("lack accepted evidence" in reason for reason in reasons)
    assert any("Certification count" in reason for reason in reasons)


def test_duplicate_or_missing_ids_cannot_be_certified() -> None:
    report = deepcopy(release_inventory())
    report["items"][1]["id"] = report["items"][0]["id"]
    reasons = release_gate_failures(report, CANDIDATE)
    assert any("exactly once" in reason for reason in reasons)


def test_candidate_and_scope_mismatch_block_release() -> None:
    report = deepcopy(release_inventory())
    report["verified_candidate"] = "2" * 40
    report["profile"] = "cloud_saas"
    reasons = release_gate_failures(report, CANDIDATE)
    assert any("self-host profile" in reason for reason in reasons)
    assert any("exact candidate" in reason for reason in reasons)
