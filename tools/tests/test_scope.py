from pathlib import Path

from tools.check_scope import find_scope_violations


def test_scope_checker_accepts_product_neutral_runtime(tmp_path: Path) -> None:
    source = tmp_path / "apps" / "api" / "neutral.py"
    source.parent.mkdir(parents=True)
    source.write_text("class Organization: pass\n", encoding="utf-8")

    assert find_scope_violations(tmp_path) == []


def test_scope_checker_rejects_gis_or_vertical_runtime_markers(tmp_path: Path) -> None:
    source = tmp_path / "apps" / "web" / "src" / "bad.ts"
    source.parent.mkdir(parents=True)
    source.write_text('import "maplibre-gl"; // house-number\n', encoding="utf-8")

    violations = find_scope_violations(tmp_path)

    assert len(violations) == 2
    assert any("map rendering engine" in item for item in violations)
    assert any("house-numbering vertical" in item for item in violations)
