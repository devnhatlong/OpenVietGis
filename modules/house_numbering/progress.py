"""Safe XLSX progress report generation without optional office dependencies."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable
from html import escape
from typing import Any


def _safe_text(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text[:32767]


def _cell(ref: str, value: Any) -> str:
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return (
        f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
        f"{escape(_safe_text(value))}</t></is></c>"
    )


def _col_name(index: int) -> str:
    result = ""
    n = index
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def build_progress_xlsx(
    *, summary: dict[str, Any], rows: Iterable[dict[str, Any]]
) -> bytes:
    columns = [
        "building_id",
        "route_name",
        "house_number",
        "condition",
        "state",
        "updated_at",
    ]
    matrix: list[list[Any]] = [
        ["Chỉ số", "Giá trị"],
        *[[key, value] for key, value in summary.items()],
        [],
        columns,
    ]
    for row in rows:
        matrix.append([row.get(column) for column in columns])
    sheet_rows: list[str] = []
    for r_idx, row in enumerate(matrix, start=1):
        cells = "".join(
            _cell(f"{_col_name(c_idx)}{r_idx}", value)
            for c_idx, value in enumerate(row, start=1)
        )
        sheet_rows.append(f'<row r="{r_idx}">{cells}</row>')
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Tiến độ" sheetId="1" r:id="rId1"/></sheets></workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return out.getvalue()
