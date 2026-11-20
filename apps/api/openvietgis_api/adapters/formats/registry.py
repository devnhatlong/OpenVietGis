"""Content-based format registry implementing FormatCodecPort."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from openvietgis_api.adapters.formats.geojson import (
    inspect_geojson,
    parse_geojson,
    write_geojson,
)
from openvietgis_api.adapters.formats.geopackage import (
    inspect_geopackage,
    parse_geopackage_member,
    write_geopackage,
)
from openvietgis_api.adapters.formats.shapefile_zip import (
    inspect_shapefile_zip,
    parse_shapefile_member,
    write_shapefile_zip,
)
from openvietgis_api.domains.spatial.domain import NativeGeometry
from openvietgis_api.domains.transfers.domain import (
    ExportFieldMapping,
    InspectedMember,
    ParsedMemberData,
    TransferFormat,
)
from openvietgis_api.domains.transfers.ports import TransferFormatError


class VectorFormatRegistry:
    def detect_format(self, data: bytes) -> TransferFormat:
        if data.startswith(b"SQLite format 3\x00"):
            return TransferFormat.GEOPACKAGE
        if data.startswith(b"PK\x03\x04") or data.startswith(b"PK\x05\x06"):
            return TransferFormat.SHAPEFILE_ZIP
        stripped = data.lstrip()
        if stripped.startswith(b"{"):
            return TransferFormat.GEOJSON
        raise TransferFormatError(
            "UNSUPPORTED_FORMAT",
            "Unrecognized file content; supported formats are GeoPackage, "
            "RFC 7946 GeoJSON, and ZIP Shapefile.",
        )

    def list_members(
        self, fmt: TransferFormat, data: bytes, *, encoding: str | None = None
    ) -> tuple[InspectedMember, ...]:
        if fmt == TransferFormat.GEOPACKAGE:
            return inspect_geopackage(data)
        if fmt == TransferFormat.GEOJSON:
            return inspect_geojson(data)
        return inspect_shapefile_zip(data, encoding=encoding)

    def parse_member(
        self,
        fmt: TransferFormat,
        data: bytes,
        *,
        member_name: str,
        declared_crs: int | None = None,
        declared_encoding: str | None = None,
    ) -> ParsedMemberData:
        if fmt == TransferFormat.GEOPACKAGE:
            return parse_geopackage_member(data, member_name=member_name, declared_crs=declared_crs)
        if fmt == TransferFormat.GEOJSON:
            if member_name != "features":
                raise TransferFormatError("UNKNOWN_MEMBER", "GeoJSON member must be 'features'.")
            return parse_geojson(data)
        return parse_shapefile_member(
            data,
            member_name=member_name,
            declared_crs=declared_crs,
            declared_encoding=declared_encoding,
        )

    def write_dataset(
        self,
        fmt: TransferFormat,
        *,
        layer_name: str,
        crs_code: int,
        geometry_family: str,
        field_mappings: Sequence[ExportFieldMapping],
        features: Sequence[tuple[str, dict[str, Any], NativeGeometry]],
    ) -> tuple[bytes, str, str]:
        if fmt == TransferFormat.GEOPACKAGE:
            return write_geopackage(
                layer_name=layer_name,
                crs_code=crs_code,
                geometry_family=geometry_family,
                field_mappings=field_mappings,
                features=features,
            )
        if fmt == TransferFormat.GEOJSON:
            return write_geojson(field_mappings=field_mappings, features=features)
        return write_shapefile_zip(
            layer_name=layer_name,
            crs_code=crs_code,
            geometry_family=geometry_family,
            field_mappings=field_mappings,
            features=features,
        )
