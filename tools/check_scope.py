from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOTS = (ROOT / "apps", ROOT / "packages")
SKIP_DIRS = {"node_modules", ".venv", "dist", "build", "coverage", "__pycache__", "generated"}
TEXT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".toml"}
FORBIDDEN_MARKERS = {
    "maplibre": "map rendering engine",
    "terra-draw": "GIS editing engine",
    "terradraw": "GIS editing engine",
    "geoserver": "OGC server",
    "martin": "tile server",
    "house-number": "house-numbering vertical",
    "house_number": "house-numbering vertical",
    "binh-hung": "legacy vertical",
    "customrolebuilder": "custom-role builder",
    "publicsharelink": "public/anonymous sharing",
}


def find_scope_violations(root: Path = ROOT) -> list[str]:
    violations: list[str] = []
    for runtime_root in (root / "apps", root / "packages"):
        if not runtime_root.exists():
            continue
        for path in runtime_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(runtime_root).parts):
                continue
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            for marker, label in FORBIDDEN_MARKERS.items():
                if marker in content:
                    violations.append(
                        f"{path.relative_to(root).as_posix()} contains out-of-scope {label} marker "
                        f"{marker!r}"
                    )
    return violations


def main() -> int:
    violations = find_scope_violations()
    if violations:
        for violation in violations:
            print(f"SCOPE VIOLATION: {violation}")
        return 1
    print("Spec 002 runtime scope: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
