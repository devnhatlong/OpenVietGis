"""Exact lost acknowledgement identity and bounded rebase report regressions."""

from uuid import uuid4

import pytest

from openvietgis_api.domains.collaboration.domain import (
    analyze_draft_conflicts,
    validate_rebase_draft,
)
from openvietgis_api.domains.editing.domain import (
    EditOperationInput,
    EditOpType,
    changeset_request_digest,
)
from openvietgis_api.domains.platform_errors import PlatformValidationError


def test_digest_is_exact_and_key_order_independent():
    def digest(ops, summary="summary", reverted=None):
        return changeset_request_digest(
            base_content_revision="a" * 64,
            summary=summary,
            operations=ops,
            reverted_from_changeset_id=reverted,
        )

    first = EditOperationInput(EditOpType.UPDATE, "feature", properties={"x": 1, "y": False})
    same = EditOperationInput(EditOpType.UPDATE, "feature", properties={"y": False, "x": 1})
    changed = EditOperationInput(EditOpType.UPDATE, "feature", properties={"x": 1, "y": True})
    assert digest([first]) == digest([same])
    assert digest([first]) != digest([changed])
    assert digest([first]) != digest([first], summary="changed")
    assert digest([first]) != digest([first], reverted=uuid4())
    assert digest([first, same]) != digest([first])
    assert digest([]) != digest([first])
    nonfinite = EditOperationInput(EditOpType.UPDATE, "feature", properties={"x": float("nan")})
    with pytest.raises(PlatformValidationError):
        digest([nonfinite])


@pytest.mark.parametrize(
    "ops",
    [
        [],
        [{"op_type": "unknown", "feature_id": "p"}],
        [{"op_type": "update", "feature_id": None}],
        [{"op_type": "update", "feature_id": "p"}] * 2001,
        [{"op_type": "update", "feature_id": "p"}, {"op_type": "delete", "feature_id": "p"}],
    ],
)
def test_draft_is_bounded_and_typed(ops):
    with pytest.raises(PlatformValidationError):
        validate_rebase_draft(ops)


def test_rebase_is_advisory_and_detects_existence_conflicts():
    ops = validate_rebase_draft(
        [
            {"op_type": "update", "feature_id": "prior"},
            {"op_type": "update", "feature_id": "intervening"},
            {"op_type": "create", "feature_id": "duplicate"},
            {"op_type": "delete", "feature_id": "absent"},
            {"op_type": "create", "feature_id": "new"},
        ]
    )
    result = analyze_draft_conflicts(
        draft_operations=ops,
        current_content_revision="b" * 64,
        intervening_changed_feature_ids={"intervening"},
        existing_feature_ids={"prior", "intervening", "duplicate"},
    )
    assert [op["feature_id"] for op in result["reapplicable_operations"]] == ["prior", "new"]
    assert [op["feature_id"] for op in result["conflicts"]] == [
        "intervening",
        "duplicate",
        "absent",
    ]
