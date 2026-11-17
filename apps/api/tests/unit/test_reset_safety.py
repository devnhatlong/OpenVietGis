import pytest
from tools.reset_dev import assert_safe_target


@pytest.mark.parametrize("database", ["openvietgis", "openvietgis_dev", "openvietgis_test"])
def test_accepts_only_documented_local_reset_databases(database: str) -> None:
    assert_safe_target(
        "development",
        f"postgresql+psycopg://user:pass@localhost:54329/{database}",
    )


@pytest.mark.parametrize(
    ("environment", "url"),
    [
        ("production", "postgresql+psycopg://user:pass@localhost/openvietgis"),
        ("development", "postgresql+psycopg://user:pass@db.example.com/openvietgis"),
        ("test", "postgresql+psycopg://user:pass@localhost/customer_prod"),
        ("test", "postgresql+psycopg://u:p@localhost/openvietgis_test?dbname=customer_prod"),
        ("test", "postgresql+psycopg://u:p@localhost/openvietgis_test?host=live.example.com"),
        ("test", "postgresql+psycopg://u:p@localhost/openvietgis_test?hostaddr=192.0.2.1"),
        ("test", "postgresql+psycopg://u:p@localhost/openvietgis_test?service=live"),
        ("test", "mysql://u:p@localhost/openvietgis_test"),
        ("development", "postgresql+psycopg://user:pass@localhost/openvietgis_prod"),
        ("test", "postgresql+psycopg://user:pass@localhost/openvietgis_customer_live"),
        ("development", "postgresql+psycopg://user:pass@localhost/openvietgis_dev_live"),
        ("test", "postgresql+psycopg://user:pass@localhost/openvietgis2"),
    ],
)
def test_rejects_unsafe_targets(environment: str, url: str) -> None:
    with pytest.raises(RuntimeError, match="Refusing reset"):
        assert_safe_target(environment, url)
