from pathlib import Path

from tools.check_architecture import find_violations

FIXTURES = Path(__file__).parent / "fixtures"


def test_rejects_core_to_vertical_module_dependency() -> None:
    violations = find_violations(FIXTURES / "invalid_core_to_module")

    assert violations
    assert any("apps/core/bad.ts" in violation for violation in violations)


def test_accepts_module_to_public_contract_dependency() -> None:
    assert find_violations(FIXTURES / "valid_module_to_contract") == []


def test_core_validation_succeeds_when_modules_directory_is_absent(tmp_path: Path) -> None:
    core = tmp_path / "apps" / "core"
    core.mkdir(parents=True)
    (core / "index.py").write_text("VALUE = 1\n", encoding="utf-8")

    assert find_violations(tmp_path) == []
