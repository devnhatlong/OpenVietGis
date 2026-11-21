"""Apply independent migrations for trusted official modules after Core migrations."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "modules"


def migrate_official_modules() -> list[str]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    migrated: list[str] = []
    if not MODULES.is_dir():
        return migrated

    for directory in sorted(path for path in MODULES.iterdir() if path.is_dir()):
        manifest_path = directory / "manifest.json"
        migrate_path = directory / "migrate.py"
        if not manifest_path.is_file() or not migrate_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        extension_key = manifest.get("extension_key")
        if extension_key != directory.name:
            raise RuntimeError(
                f"module directory {directory.name!r} does not match "
                f"manifest extension_key {extension_key!r}"
            )
        module = importlib.import_module(f"modules.{directory.name}.migrate")
        upgrade = getattr(module, "upgrade", None)
        if not callable(upgrade):
            raise TypeError(f"module {directory.name!r} migrate.py has no upgrade()")
        upgrade()
        migrated.append(directory.name)
    return migrated


def main() -> int:
    migrated = migrate_official_modules()
    if migrated:
        print("Official module migrations applied: " + ", ".join(migrated))
    else:
        print("No official module migrations to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
