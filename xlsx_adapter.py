#!/usr/bin/env python3
"""Build a canonical relationship graph from XLSX exports using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from import_report import ImportReport, ImportRecordError, validate_output_paths, write_report, write_text_atomic, IMPORT_ERRORS
from xml.etree import ElementTree as ET

from csv_adapter import (
    _merge_node, render, required_identity_columns,
    check_identity_headers, check_identity_values,
)


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_REF = re.compile(r"([A-Z]+)([0-9]+)")
MAX_XLSX_COLUMN = 16384
MAX_XLSX_ROW = 1048576


def _cell_position(cell_ref: str) -> tuple[int, int]:
    match = CELL_REF.fullmatch(cell_ref.upper())
    if not match:
        raise ValueError(f"invalid XLSX cell reference: {cell_ref!r}")
    column = 0
    for char in match.group(1):
        column = column * 26 + (ord(char) - ord("A") + 1)
    row = int(match.group(2))
    if not 1 <= column <= MAX_XLSX_COLUMN or not 1 <= row <= MAX_XLSX_ROW:
        raise ValueError(f"XLSX cell reference outside worksheet limits: {cell_ref!r}")
    return column - 1, row


def _column_index(cell_ref: str) -> int:
    return _cell_position(cell_ref)[0]


def _row_number(value: str | None, previous: int, location: str) -> int:
    if value is None or re.fullmatch(r"[0-9]+", value) is None:
        raise ValueError(f"{location}: adapter requires an explicit decimal row coordinate")
    number = int(value)
    if not 1 <= number <= MAX_XLSX_ROW:
        raise ValueError(f"{location}: row coordinate outside worksheet limits: {value!r}")
    if number <= previous:
        raise ValueError(f"{location}: row coordinates must be unique and increasing: {value!r} after {previous}")
    return number


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in book.namelist():
        return []
    root = ET.fromstring(book.read(name))
    result = []
    for item in root.findall(f"{{{MAIN_NS}}}si"):
        result.append("".join(text.text or "" for text in item.iter(f"{{{MAIN_NS}}}t")))
    return result


def _sheet_paths(book: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
        if rel.attrib.get("Id") and rel.attrib.get("Target")
    }
    result = {}
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        name = sheet.attrib.get("name")
        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        if not name or not rel_id or rel_id not in targets:
            continue
        target = targets[rel_id].lstrip("/")
        result[name] = str(PurePosixPath("xl") / target) if not target.startswith("xl/") else target
    return result


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(f"{{{MAIN_NS}}}t"))
    value = cell.find(f"{{{MAIN_NS}}}v")
    raw = value.text if value is not None and value.text is not None else ""
    if cell_type == "s" and raw:
        index = int(raw)
        if index < 0 or index >= len(shared):
            raise ValueError(f"shared string index out of range: {index}")
        return shared[index]
    if cell_type == "b":
        if not raw.strip():
            return ""
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def read_sheet(path: Path, sheet_name: str, *, required_columns: tuple[str, ...] = (), report: ImportReport | None = None) -> Iterator[tuple[int, dict[str, str]]]:
    with zipfile.ZipFile(path) as book:
        sheets = _sheet_paths(book)
        if sheet_name not in sheets:
            raise ValueError(f"worksheet {sheet_name!r} not found in {path.name!r}; available: {sorted(sheets)}")
        shared = _shared_strings(book)
        root = ET.fromstring(book.read(sheets[sheet_name]))
        header: list[str] | None = None
        previous_row = 0

        for row in root.findall(f".//{{{MAIN_NS}}}row"):
            location = f"XLSX {path.name!r}, sheet {sheet_name!r}"
            row_number = _row_number(row.attrib.get("r"), previous_row, location)
            previous_row = row_number
            if report is not None and header is not None:
                report.row(row_number)
            cells: dict[int, str] = {}
            for cell in row.findall(f"{{{MAIN_NS}}}c"):
                ref = cell.attrib.get("r")
                cell_location = f"{location}, row {row_number}"
                if not ref:
                    raise ImportRecordError(f"{cell_location}: adapter requires an explicit cell reference", "missing_cell_reference")
                try:
                    column, cell_row = _cell_position(ref)
                except ValueError as exc:
                    raise ImportRecordError(f"{cell_location}: {exc}", "invalid_cell_reference") from exc
                if cell_row != row_number:
                    raise ImportRecordError(f"{cell_location}: cell {ref!r} belongs to row {cell_row}", "cell_row_mismatch")
                if column in cells:
                    raise ImportRecordError(f"{cell_location}: duplicate cell coordinate {ref!r}", "duplicate_cell_coordinate")
                cells[column] = _cell_value(cell, shared)
            if not cells:
                if report is not None and header is not None:
                    report.record("skipped", "blank_record")
                continue
            values = [cells.get(index, "") for index in range(max(cells) + 1)]
            if header is None:
                header = [str(value).strip() for value in values]
                if not any(header):
                    raise ValueError(f"worksheet {sheet_name!r} has an empty header row")
                if any(not name for name in header):
                    raise ValueError(f"worksheet {sheet_name!r} has an empty column name")
                duplicates = sorted({name for name in header if name and header.count(name) > 1})
                if duplicates:
                    raise ValueError(f"worksheet {sheet_name!r} has duplicate headers: {duplicates}")
                check_identity_headers(header, required_columns, f"XLSX {path.name!r}, sheet {sheet_name!r}")
                continue
            if any(value for value in values[len(header):]):
                raise ValueError(f"worksheet {sheet_name!r} row {row_number} has values beyond the header")
            padded = values + [""] * max(0, len(header) - len(values))
            yield row_number, {name: padded[index] for index, name in enumerate(header) if name}

        if header is None and required_columns:
            raise ValueError(f"XLSX {path.name!r}, sheet {sheet_name!r}: required identity columns cannot be checked without a header")


def _normalizers(manifest: dict[str, Any], source: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for collection in (manifest.get("normalizers", {}), source.get("normalizers", {})):
        for field, value in collection.items():
            rules = [value] if isinstance(value, str) else list(value)
            result.setdefault(str(field), []).extend(str(rule) for rule in rules)
    return result


def _apply_rule(value: str, rule: str) -> str:
    if rule == "strip":
        return value.strip()
    if rule == "upper":
        return value.upper()
    if rule == "lower":
        return value.lower()
    if rule == "strip_leading_zeros":
        stripped = value.lstrip("0")
        return stripped or ("0" if value else "")
    raise ValueError(f"unsupported normalizer: {rule!r}")


def normalize_row(row: dict[str, str], rules: dict[str, list[str]]) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    result = dict(row)
    changes: dict[str, dict[str, str]] = {}
    for field, operations in rules.items():
        if field not in result:
            raise ValueError(f"normalizer references missing column {field!r}")
        original = str(result[field])
        value = original
        for operation in operations:
            value = _apply_rule(value, operation)
        result[field] = value
        if value != original:
            changes[field] = {"from": original, "to": value}
    return result, changes


def build_model(manifest: dict[str, Any], base_dir: Path, *, import_report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = ImportReport(import_report, "xlsx", manifest)
    try:
        model = _build_model(manifest, base_dir, report)
    except IMPORT_ERRORS as exc:
        report.abort(exc)
        raise
    report.finish()
    return model


def _build_model(manifest: dict[str, Any], base_dir: Path, report: ImportReport) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []

    for source_index, source in enumerate(manifest.get("node_sources", [])):
        report.source("node_sources", source_index)
        file_name = source["file"]
        sheet = str(source.get("sheet", "Sheet1"))
        rules = _normalizers(manifest, source)
        columns = required_identity_columns(source, f"XLSX {file_name!r}, sheet {sheet!r}")
        for row_number, raw_row in read_sheet(base_dir / file_name, sheet, required_columns=columns, report=report):
            if not any(value.strip() for value in raw_row.values()):
                report.record("skipped", "blank_record")
                continue
            row, changes = normalize_row(raw_row, rules)
            check_identity_values(row, columns, f"XLSX {file_name!r}, sheet {sheet!r}, row {row_number}")
            raw_id = render(source["id"], raw_row).strip()
            node_id = render(source["id"], row).strip()
            if not node_id:
                raise ImportRecordError(f"XLSX {file_name!r}, sheet {sheet!r}, row {row_number}" + ": node id renders empty", "blank_node_id")
            node: dict[str, Any] = {
                "id": node_id,
                "system": render(source.get("system", ""), row).strip(),
                "object": render(source.get("object", ""), row).strip(),
            }
            if source.get("label"):
                node["label"] = render(source["label"], row).strip()
            source_ref: dict[str, Any] = {"file": file_name, "sheet": sheet, "row": row_number}
            if raw_id != node_id:
                source_ref["raw_identity"] = raw_id
            if changes:
                source_ref["normalization"] = changes
            disposition = "node_merged" if node_id in nodes else "node_created"
            _merge_node(nodes, node, source_ref)
            report.record("accepted", disposition, {"kind": "node", "id": node_id})

    for source_index, source in enumerate(manifest.get("relationship_sources", [])):
        report.source("relationship_sources", source_index)
        file_name = source["file"]
        sheet = str(source.get("sheet", "Sheet1"))
        rules = _normalizers(manifest, source)
        columns = required_identity_columns(source, f"XLSX {file_name!r}, sheet {sheet!r}")
        for row_number, raw_row in read_sheet(base_dir / file_name, sheet, required_columns=columns, report=report):
            if not any(value.strip() for value in raw_row.values()):
                report.record("skipped", "blank_record")
                continue
            row, changes = normalize_row(raw_row, rules)
            check_identity_values(row, columns, f"XLSX {file_name!r}, sheet {sheet!r}, row {row_number}")
            from_id = render(source["from"], row).strip()
            to_id = render(source["to"], row).strip()
            if not from_id or not to_id:
                missing = ", ".join(field for field, value in (("from", from_id), ("to", to_id)) if not value)
                raise ImportRecordError(f"XLSX {file_name!r}, sheet {sheet!r}, row {row_number}" + f": relationship {missing} renders empty", "blank_relationship_endpoint")
            provenance: dict[str, Any] = {"file": file_name, "sheet": sheet, "row": row_number}
            if changes:
                provenance["normalization"] = changes
            relationships.append({
                "from": from_id,
                "to": to_id,
                "type": render(source.get("type", "related_to"), row).strip() or "related_to",
                "provenance": provenance,
            })
            report.record("accepted", "relationship_created", {
                "kind": "relationship", "index": len(relationships) - 1,
                "from": from_id, "to": to_id, "type": relationships[-1]["type"],
            })

    return {"nodes": list(nodes.values()), "relationships": relationships}


def load_manifest(path: str | Path) -> tuple[dict[str, Any], Path]:
    manifest_path = Path(path)
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    return manifest, manifest_path.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert XLSX exports into a Data Relationship Map model")
    parser.add_argument("manifest")
    parser.add_argument("--output", "-o")
    parser.add_argument("--import-report", help="Write versioned per-source row accounting (partial on import error)")
    args = parser.parse_args()
    try:
        manifest, base_dir = load_manifest(args.manifest)
        report = {} if args.import_report else None
        if args.import_report:
            validate_output_paths(Path(args.manifest), manifest, base_dir, args.output, args.import_report)
        try:
            model = build_model(manifest, base_dir, import_report=report)
        except IMPORT_ERRORS as exc:
            if args.import_report and report and report.get("status") == "aborted":
                write_report(args.import_report, report)
            raise
        if args.import_report:
            write_report(args.import_report, report)
    except IMPORT_ERRORS as exc:
        parser.error(str(exc))
    payload = json.dumps(model, indent=2)
    try:
        if args.output:
            if args.import_report:
                write_text_atomic(args.output, payload + "\n")
            else:
                Path(args.output).write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
    except OSError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
