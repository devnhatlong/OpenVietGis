"""Staged multi-format import for House Numbering evidence."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID, uuid4
from xml.etree import ElementTree as ET

import ezdxf
import shapefile
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.module_sdk import put_module_artifact
from sqlalchemy import text
from sqlalchemy.orm import Session

from modules.house_numbering.domain import validate_import_counts

_ALLOWED_FORMATS = {"csv", "xlsx", "geojson", "dxf", "shapefile_zip"}
_ALLOWED_ORIGINS = {"certificate", "cad", "survey", "legacy", "manual"}
_ALLOWED_CONFIDENCE = {"authoritative", "observed", "estimated"}


@dataclass(frozen=True, slots=True)
class ParsedImport:
    rows: list[dict[str, Any]]
    encoding: str | None


def _decode_text(data: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1258"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise PlatformValidationError("unsupported text encoding", code="IMPORT_ENCODING")


def _parse_csv(data: bytes) -> ParsedImport:
    decoded, encoding = _decode_text(data)
    sample = decoded[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(decoded), dialect=dialect)
    if not reader.fieldnames:
        raise PlatformValidationError("CSV has no header", code="IMPORT_HEADER")
    rows = [{str(k): v for k, v in row.items()} for row in reader]
    return ParsedImport(rows, encoding)


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        xml = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml)
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    result: list[str] = []
    for si in root.findall("x:si", ns):
        result.append("".join(t.text or "" for t in si.findall(".//x:t", ns)))
    return result


def _xlsx_cell_value(cell: ET.Element, shared: list[str], ns: dict[str, str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(t.text or "" for t in cell.findall(".//x:t", ns))
    value = cell.find("x:v", ns)
    raw = "" if value is None or value.text is None else value.text
    if cell_type == "s" and raw:
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return ""
    return raw


def _parse_xlsx(data: bytes) -> ParsedImport:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PlatformValidationError(
            "invalid XLSX archive", code="IMPORT_XLSX"
        ) from exc
    with archive:
        try:
            sheet_xml = archive.read("xl/worksheets/sheet1.xml")
        except KeyError as exc:
            raise PlatformValidationError(
                "XLSX first sheet missing", code="IMPORT_XLSX"
            ) from exc
        shared = _xlsx_shared_strings(archive)
        root = ET.fromstring(sheet_xml)
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        matrix: list[list[str]] = []
        for row in root.findall(".//x:sheetData/x:row", ns):
            values = [
                _xlsx_cell_value(cell, shared, ns) for cell in row.findall("x:c", ns)
            ]
            matrix.append(values)
    if not matrix or not any(str(v).strip() for v in matrix[0]):
        raise PlatformValidationError("XLSX has no header", code="IMPORT_HEADER")
    header = [str(v).strip() for v in matrix[0]]
    rows: list[dict[str, Any]] = []
    for values in matrix[1:]:
        padded = values + [""] * (len(header) - len(values))
        rows.append({header[i]: padded[i] for i in range(len(header)) if header[i]})
    return ParsedImport(rows, None)


def _parse_geojson(data: bytes) -> ParsedImport:
    decoded, encoding = _decode_text(data)
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise PlatformValidationError("invalid GeoJSON", code="IMPORT_GEOJSON") from exc
    if payload.get("type") != "FeatureCollection" or not isinstance(
        payload.get("features"), list
    ):
        raise PlatformValidationError(
            "GeoJSON FeatureCollection required", code="IMPORT_GEOJSON"
        )
    rows: list[dict[str, Any]] = []
    for feature in payload["features"]:
        properties = dict(feature.get("properties") or {})
        geometry = feature.get("geometry")
        properties["_geometry"] = geometry
        if isinstance(geometry, dict) and geometry.get("type") == "Point":
            coords = geometry.get("coordinates")
            if isinstance(coords, list) and len(coords) >= 2:
                properties["_x"] = coords[0]
                properties["_y"] = coords[1]
        rows.append(properties)
    return ParsedImport(rows, encoding)


def _parse_dxf(data: bytes) -> ParsedImport:
    decoded, encoding = _decode_text(data)
    try:
        doc = ezdxf.read(io.StringIO(decoded))
    except Exception as exc:
        raise PlatformValidationError("invalid DXF", code="IMPORT_DXF") from exc
    rows: list[dict[str, Any]] = []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == "TEXT":
            point = entity.dxf.insert
            rows.append(
                {
                    "raw_number": entity.dxf.text,
                    "_x": float(point.x),
                    "_y": float(point.y),
                    "_entity": kind,
                }
            )
        elif kind == "MTEXT":
            point = entity.dxf.insert
            rows.append(
                {
                    "raw_number": entity.plain_text(),
                    "_x": float(point.x),
                    "_y": float(point.y),
                    "_entity": kind,
                }
            )
        elif kind == "INSERT":
            attrs = {attr.dxf.tag: attr.dxf.text for attr in entity.attribs}
            point = entity.dxf.insert
            attrs.update({"_x": float(point.x), "_y": float(point.y), "_entity": kind})
            rows.append(attrs)
    return ParsedImport(rows, encoding)


def _parse_shapefile_zip(data: bytes) -> ParsedImport:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PlatformValidationError(
            "invalid shapefile zip", code="IMPORT_SHP"
        ) from exc
    with archive:
        names = archive.namelist()
        shp_names = [n for n in names if PurePosixPath(n).suffix.lower() == ".shp"]
        if len(shp_names) != 1:
            raise PlatformValidationError(
                "zip must contain exactly one .shp", code="IMPORT_SHP"
            )
        base = str(PurePosixPath(shp_names[0]).with_suffix(""))
        members = {
            PurePosixPath(n).suffix.lower(): n
            for n in names
            if str(PurePosixPath(n).with_suffix("")) == base
        }
        if ".dbf" not in members:
            raise PlatformValidationError("shapefile DBF missing", code="IMPORT_SHP")
        reader = shapefile.Reader(
            shp=io.BytesIO(archive.read(members[".shp"])),
            shx=io.BytesIO(archive.read(members[".shx"]))
            if ".shx" in members
            else None,
            dbf=io.BytesIO(archive.read(members[".dbf"])),
        )
        fields = [field[0] for field in reader.fields[1:]]
        rows: list[dict[str, Any]] = []
        for sr in reader.iterShapeRecords():
            row = dict(zip(fields, list(sr.record), strict=False))
            if sr.shape.shapeType in {1, 11, 21} and sr.shape.points:
                row["_x"], row["_y"] = sr.shape.points[0][:2]
            row["_shape_type"] = int(sr.shape.shapeType)
            rows.append(row)
        reader.close()
    return ParsedImport(rows, None)


def parse_import(source_format: str, data: bytes) -> ParsedImport:
    if source_format not in _ALLOWED_FORMATS:
        raise PlatformValidationError("unsupported import format", code="IMPORT_FORMAT")
    parser = {
        "csv": _parse_csv,
        "xlsx": _parse_xlsx,
        "geojson": _parse_geojson,
        "dxf": _parse_dxf,
        "shapefile_zip": _parse_shapefile_zip,
    }[source_format]
    return parser(data)


def _parse_uuid(value: Any) -> UUID | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return UUID(str(value).strip())
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


class HouseNumberingImporter:
    def __init__(self, session: Session, context: AuthorizationContext) -> None:
        self.session = session
        self.context = context
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        self.org = context.organization_id
        self.project = context.project_id
        self.actor = context.actor.actor_id

    def _prepare(self) -> None:
        from modules.house_numbering.persistence import HouseNumberingRepository

        HouseNumberingRepository(self.session, self.context).prepare("edit")

    def stage(
        self,
        *,
        filename: str,
        source_format: str,
        origin: str,
        data: bytes,
        mapping: dict[str, str],
        source_crs: int | None,
        default_source_reference: str,
        default_confidence: str = "observed",
    ) -> dict[str, Any]:
        self._prepare()
        if origin not in _ALLOWED_ORIGINS:
            raise PlatformValidationError(
                "invalid evidence origin", code="IMPORT_ORIGIN"
            )
        if default_confidence not in _ALLOWED_CONFIDENCE:
            raise PlatformValidationError(
                "invalid evidence confidence", code="IMPORT_CONFIDENCE"
            )
        fingerprint_payload = json.dumps(
            {
                "source_format": source_format,
                "origin": origin,
                "mapping": mapping,
                "source_crs": source_crs,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        fingerprint = sha256(data + b"\0" + fingerprint_payload).hexdigest()
        existing = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.import_batches
                WHERE organization_id=:org AND project_id=:project AND source_fingerprint=:fp
            """),
                {"org": self.org, "project": self.project, "fp": fingerprint},
            )
            .mappings()
            .first()
        )
        if existing is not None:
            return {"batch": dict(existing), "replayed": True, "rejections": []}

        parsed = parse_import(source_format, data)
        artifact = put_module_artifact(
            self.context,
            namespace="house-numbering-imports",
            filename=filename,
            content_type="application/octet-stream",
            data=data,
        )
        accepted = 0
        rejected = 0
        rejections: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        batch_id = uuid4()
        for index, source_row in enumerate(parsed.rows, start=2):

            def value(name: str, row: dict[str, Any] = source_row) -> Any:
                column = mapping.get(name)
                if column is None:
                    return None
                return row.get(column)

            building_id = _parse_uuid(value("building_id"))
            route_id = _parse_uuid(value("route_id"))
            raw_number_val = value("raw_number")
            if raw_number_val is None:
                raw_number_val = value("old_number") or value("new_number")
            raw_number = (
                str(raw_number_val).strip() if raw_number_val is not None else None
            )
            source_reference_val = value("source_reference")
            source_reference = (
                str(source_reference_val).strip()
                if source_reference_val is not None
                and str(source_reference_val).strip()
                else default_source_reference.strip()
            )
            confidence_val = value("confidence")
            confidence = (
                str(confidence_val).strip().lower()
                if confidence_val is not None and str(confidence_val).strip()
                else default_confidence
            )
            evidence_date = _parse_date(value("evidence_date"))
            reasons: list[str] = []
            if not source_reference:
                reasons.append("missing_source_reference")
            if confidence not in _ALLOWED_CONFIDENCE:
                reasons.append("invalid_confidence")
            if raw_number is None or not raw_number:
                reasons.append("missing_number")
            if value("building_id") not in (None, "") and building_id is None:
                reasons.append("invalid_building_id")
            if value("route_id") not in (None, "") and route_id is None:
                reasons.append("invalid_route_id")
            if reasons:
                rejected += 1
                rejections.append({"row": index, "reasons": reasons})
                continue
            self.session.execute(
                text("""
                    INSERT INTO house_numbering.evidence (
                        id,organization_id,project_id,building_id,route_id,origin,raw_number,
                        source_reference,evidence_date,confidence,private_ref,
                        created_by_actor_id,created_at
                    ) VALUES (
                        :id,:org,:project,:building,:route,:origin,:raw_number,
                        :source_reference,:evidence_date,:confidence,NULL,:actor,:now
                    )
                """),
                {
                    "id": uuid4(),
                    "org": self.org,
                    "project": self.project,
                    "building": building_id,
                    "route": route_id,
                    "origin": origin,
                    "raw_number": raw_number,
                    "source_reference": source_reference,
                    "evidence_date": evidence_date,
                    "confidence": confidence,
                    "actor": self.actor,
                    "now": now,
                },
            )
            accepted += 1
        validate_import_counts(len(parsed.rows), accepted, rejected)
        row = (
            self.session.execute(
                text("""
                INSERT INTO house_numbering.import_batches (
                    id,organization_id,project_id,source_fingerprint,source_name,source_crs,
                    mapping,read_count,accepted_count,rejected_count,original_artifact_id,
                    status,created_by_actor_id,created_at,committed_at
                ) VALUES (
                    :id,:org,:project,:fp,:name,:crs,CAST(:mapping AS jsonb),:read,:accepted,
                    :rejected,:artifact,'committed',:actor,:now,:now
                ) RETURNING *
            """),
                {
                    "id": batch_id,
                    "org": self.org,
                    "project": self.project,
                    "fp": fingerprint,
                    "name": filename,
                    "crs": source_crs,
                    "mapping": json.dumps(
                        {
                            **mapping,
                            "source_format": source_format,
                            "origin": origin,
                            "encoding": parsed.encoding,
                        }
                    ),
                    "read": len(parsed.rows),
                    "accepted": accepted,
                    "rejected": rejected,
                    "artifact": artifact.id,
                    "actor": self.actor,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self.session.commit()
        return {"batch": dict(row), "replayed": False, "rejections": rejections}

    def list_batches(self) -> list[dict[str, Any]]:
        self._prepare()
        rows = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.import_batches
                WHERE organization_id=:org AND project_id=:project
                ORDER BY created_at DESC,id DESC
            """),
                {"org": self.org, "project": self.project},
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]
