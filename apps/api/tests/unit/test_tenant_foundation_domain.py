import pytest
from pydantic import ValidationError

from openvietgis_api.adapters.http.projects import CreateProjectRequest
from openvietgis_api.domains.tenancy.service import _clean_name


def test_real_project_name_is_trimmed() -> None:
    assert _clean_name("  foundation-check  ") == "foundation-check"
    assert CreateProjectRequest(name="  foundation-check  ", slug="foundation").name == (
        "foundation-check"
    )


@pytest.mark.parametrize("name", ["", " ", "\t\n"])
def test_real_project_rejects_blank_name(name: str) -> None:
    with pytest.raises(ValueError, match="name is required"):
        _clean_name(name)
    with pytest.raises(ValidationError):
        CreateProjectRequest(name=name, slug="valid")


def test_real_project_rejects_overlong_unicode_name() -> None:
    with pytest.raises(ValidationError):
        CreateProjectRequest(name="đ" * 201, slug="valid")
