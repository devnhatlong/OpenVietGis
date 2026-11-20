"""Strict EPSG WKT1/PRJ definitions and recognition for R003/R005 approved CRS profiles."""

from __future__ import annotations

import re

EPSG_WKT1: dict[int, str] = {
    4326: (
        'GEOGCS["WGS 84",DATUM["WGS_1984",'
        'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],'
        'AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],'
        'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
        'AUTHORITY["EPSG","4326"]]'
    ),
    3857: (
        'PROJCS["WGS 84 / Pseudo-Mercator",GEOGCS["WGS 84",DATUM["WGS_1984",'
        'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],'
        'AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],'
        'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
        'AUTHORITY["EPSG","4326"]],PROJECTION["Mercator_1SP"],'
        'PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],'
        'PARAMETER["false_easting",0],PARAMETER["false_northing",0],'
        'UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],'
        'AXIS["Northing",NORTH],AUTHORITY["EPSG","3857"]]'
    ),
    4756: (
        'GEOGCS["VN-2000",DATUM["Vietnam_2000",'
        'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],'
        'AUTHORITY["EPSG","6756"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],'
        'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
        'AUTHORITY["EPSG","4756"]]'
    ),
    5899: (
        'PROJCS["VN-2000 / TM-3 107-45",GEOGCS["VN-2000",DATUM["Vietnam_2000",'
        'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],'
        'AUTHORITY["EPSG","6756"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],'
        'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
        'AUTHORITY["EPSG","4756"]],PROJECTION["Transverse_Mercator"],'
        'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",107.75],'
        'PARAMETER["scale_factor",0.9999],PARAMETER["false_easting",500000],'
        'PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],'
        'AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","5899"]]'
    ),
}

EPSG_NAMES: dict[int, str] = {
    4326: "WGS 84",
    3857: "WGS 84 / Pseudo-Mercator",
    4756: "VN-2000",
    5899: "VN-2000 / TM-3 107-45",
}

_TRAILING_AUTH_RE = re.compile(
    r'AUTHORITY\["EPSG"\s*,\s*"(\d+)"\]\s*\]\s*$|ID\["EPSG"\s*,\s*(\d+)\]\s*\]\s*$'
)


def parse_prj_to_epsg(prj_text: str) -> int | None:
    """Strictly recognize approved EPSG codes from WKT/PRJ; never guess ambiguous VN-2000."""
    text = prj_text.strip()
    if not text:
        return None
    match = _TRAILING_AUTH_RE.search(text)
    if match:
        code = int(match.group(1) or match.group(2))
        return code if code in EPSG_WKT1 else None
    upper = text.upper()
    if upper.startswith("GEOGCS[") and (
        '"WGS_1984"' in upper or '"GCS_WGS_1984"' in upper or '"WGS 84"' in upper
    ):
        if 'DATUM["WGS_1984"' in upper or 'DATUM["D_WGS_1984"' in upper:
            return 4326
    if upper.startswith("PROJCS[") and (
        "PSEUDO-MERCATOR" in upper or "MERCATOR_AUXILIARY_SPHERE" in upper
    ):
        return 3857
    if upper.startswith("GEOGCS[") and "VIETNAM_2000" in upper:
        return 4756
    if (
        upper.startswith("PROJCS[")
        and "VIETNAM_2000" in upper
        and 'PARAMETER["CENTRAL_MERIDIAN",107.75]' in upper.replace(" ", "")
        and 'PARAMETER["SCALE_FACTOR",0.9999]' in upper.replace(" ", "")
        and 'PARAMETER["FALSE_EASTING",500000]' in upper.replace(" ", "")
    ):
        return 5899
    return None
