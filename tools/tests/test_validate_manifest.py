import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_root_validation_manifest_contains_all_mandatory_categories() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]

    assert "validate" in scripts
    for category in (
        "validate:runtime",
        "validate:ts",
        "validate:py",
        "validate:arch",
        "validate:docs",
        "validate:integration",
        "validate:e2e",
    ):
        assert category in scripts
        assert category in scripts["validate"]