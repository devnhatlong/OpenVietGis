from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
CONTRACT = ROOT / "specs" / "001-platform-foundation" / "contracts" / "foundation-api.yaml"


def test_foundation_openapi_contract_contains_required_paths() -> None:
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))

    assert document["openapi"] == "3.1.0"
    assert set(document["paths"]) == {
        "/health/live",
        "/health/ready",
        "/foundation-records",
        "/foundation-records/{record_id}",
    }
    create_schema = document["components"]["schemas"]["FoundationRecordCreate"]
    assert create_schema["properties"]["label"]["minLength"] == 1
    assert create_schema["properties"]["label"]["maxLength"] == 120
