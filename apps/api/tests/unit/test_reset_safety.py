import pytest
from tools.reset_dev import assert_safe_target


def test_accepts_local_development_database() -> None:
    assert_safe_target(
        "development",
        "postgresql+psycopg://user:pass@localhost:54329/openvietgis",
    )


@pytest.mark.parametrize(
    ("environment", "url"),
    [
        ("production", "postgresql+psycopg://user:pass@localhost/openvietgis"),
        ("development", "postgresql+psycopg://user:pass@db.example.com/openvietgis"),
        ("test", "postgresql+psycopg://user:pass@localhost/customer_prod"),
    ],
)
def test_rejects_unsafe_targets(environment: str, url: str) -> None:
    with pytest.raises(RuntimeError, match="Refusing reset"):
        assert_safe_target(environment, url)
