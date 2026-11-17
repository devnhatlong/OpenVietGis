from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json"}
MODULE_MARKERS = ("modules.", "modules/", "@openvietgis/module-")
ADAPTER_MARKERS = ("openvietgis_api.adapters", "openvietgis_api/adapters")
SKIP_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}


def find_violations(root: Path = ROOT) -> list[str]:
    violations: list[str] = []
    for core_root in (root / "apps", root / "packages"):
        if not core_root.exists():
            continue
        for path in core_root.rglob("*"):
            relative_parts = path.relative_to(core_root).parts
            if any(part in SKIP_DIRS for part in relative_parts):
                continue
            if not path.is_file() or path.suffix not in TEXT_EXTENSIONS:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            if any(marker in content for marker in MODULE_MARKERS):
                violations.append(
                    f"{path.relative_to(root).as_posix()} references vertical module code"
                )
            relative_to_root = path.relative_to(root).as_posix()
            if (
                relative_to_root.startswith("apps/api/openvietgis_api/domains/")
                and any(marker in content for marker in ADAPTER_MARKERS)
            ):
                violations.append(
                    f"{relative_to_root} imports infrastructure adapter code from a domain"
                )
    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        for violation in violations:
            print(f"ARCHITECTURE VIOLATION: {violation}")
        return 1
    print("Architecture boundaries: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())