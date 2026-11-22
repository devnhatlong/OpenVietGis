"""Public R006 callers cannot forge the internal R013 durable recovery IDs."""

import pytest
from pydantic import ValidationError

from openvietgis_api.adapters.http.editing import (
    CommitChangesetRequest,
    RevertChangesetRequest,
)


@pytest.mark.parametrize("operation_id", ["field-sync-spoof", "field-sync-"])
def test_internal_operation_id_reserved(operation_id: str) -> None:
    with pytest.raises(ValidationError, match="reserved internal"):
        CommitChangesetRequest(
            base_content_revision="v1",
            operation_id=operation_id,
            operations=[],
        )
    with pytest.raises(ValidationError, match="reserved internal"):
        RevertChangesetRequest(operation_id=operation_id)


def test_normal_operations_unchanged() -> None:
    assert RevertChangesetRequest(operation_id="ordinary").operation_id == "ordinary"
