import pytest

from openvietgis_api.domain.foundation import FoundationSampleRecord


def test_create_trims_label_and_sets_stable_fields() -> None:
    record = FoundationSampleRecord.create("  foundation-check  ")

    assert record.label == "foundation-check"
    assert record.id is not None
    assert record.created_at == record.updated_at
    assert record.created_at.tzinfo is not None


@pytest.mark.parametrize("label", ["", " ", "\t\n"])
def test_create_rejects_blank_label(label: str) -> None:
    with pytest.raises(ValueError, match="blank"):
        FoundationSampleRecord.create(label)


def test_create_rejects_label_over_120_unicode_characters() -> None:
    with pytest.raises(ValueError, match="120"):
        FoundationSampleRecord.create("đ" * 121)
