"""Independent Land & Asset Management reference workflow (strictly outside Core)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path(__file__).with_name("manifest.json")


def load_manifest() -> dict[str, Any]:
    return dict(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def build_inspection_payload(
    *,
    asset_code: str,
    land_use_code: str,
    area_m2: float,
    condition_score: int,
    inspector_note: str = "",
) -> dict[str, Any]:
    return {
        "asset_code": asset_code,
        "land_use_code": land_use_code,
        "area_m2": area_m2,
        "condition_score": condition_score,
        "inspector_note": inspector_note,
    }
