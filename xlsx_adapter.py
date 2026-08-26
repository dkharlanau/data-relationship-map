#!/usr/bin/env python3
"""Build a canonical relationship graph from XLSX exports using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from xml.etree import ElementTree as ET

from csv_adapter import _merge_node, render


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_REF = re.compile(r"^([A-Z]+)(\d+)$")


def _column_index(cell_ref: str) -> int:
    match = CELL_REF.match(cell_ref.upper())
    if not match:
        raise ValueError(f"invalid XLSX cell reference: {cell_ref!r}")
    value = 0
    for char in match.group(1):
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


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
        path = str(PurePosixPath("xl") / target) if not target.startswith("xl/") else target
        result[name] = path
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
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def read_sheet(path: Path, sheet_name: str) -> Iterator[tuple[int, dict[str, str]]]:
    with zipfile.ZipFile(path) as book:
        sheets = _sheet_paths(book)
        if sheet_name not in sheets:
            raise ValueError(f"worksheet {sheet_name!r} not found in {path.name!r}; available: {sorted(sheets)}")
        shared = _shared_strings(book)
        root = ET.fromstring(book.read(sheets[sheet_name]))

        header: list[str] | None = None
        for row in root.findall(f".//{{{MAIN_NS}}}row"):
            row_number = int(row.attrib.get("r", "0") or 0)
            cells: dict[int, str] = {}
            for cell in row.findall(f"{{{MAIN_NS}}}c"):
                ref = cell.attrib.get("r")
                if not ref:
                    continue
                cells[_column_index(ref)] = _cell_value(cell, shared)
            if not cells:
                continue
            width = max(cells) + 1
            values = [cells.get(index, "") for index in range(width)]
            if header is None:
                header = [str(value).strip() for value in values]
                if not any(header):
                    raise ValueError(f"worksheet {sheet_name!r} has an empty header row")
                duplicates = sorted({name for name in header if name and header.count(name) > 1})
                if duplicates:
                    raise ValueError(f"worksheet {sheet_name!r} has duplicate headers: {duplicates}")
                continue
            padded = values + [""] * max(0, len(header) - len(values))
            yield row_number, {name: padded[index] if index < len(padded) else "" for index, name in enumerate(header) if name}


def _normalizers(manifest: dict[str, Any], source: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for collection in (manifest.get("normalizers", {}), source.get("normalizers", {})):
        for field, value in collection.items():
            rules = [value] if isinstance(value, str) else list(value)
            result[str(field)] = [str(rule) for rule in rules]
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


def build_model(manifest: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []

    for source in manifest.get("node_sources", []):
        file_name = source["file"]
        sheet = str(source.get("sheet", "Sheet1"))
        rules = _normalizers(manifest, source)
        for row_number, raw_row in read_sheet(base_dir / file_name, sheet):
            row, changes = normalize_row(raw_row, rules)
            raw_id = render(source["id"], raw_row).strip()
            node_id = render(source["id"], row).strip()
            if not node_id:
                continue
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
            _merge_node(nodes, node, source_ref)

    for source in manifest.get("relationship_sources", []):
        file_name = source["file"]
        sheet = str(source.get("sheet", "Sheet1"))
        rules = _normalizers(manifest, source)
        for row_number, raw_row in read_sheet(base_dir / file_name, sheet):
            row, changes = normalize_row(raw_row, rules)
            from_id = render(source["from"], row).strip()
            to_id = render(source["to"], row).strip()
            if not from_id or not to_id:
                continue
            provenance: dict[str, Any] = {"file": file_name, "sheet": sheet, "row": row_number}
            if changes:
                provenance["normalization"] = changes
            relationships.append({
                "from": from_id,
                "to": to_id,
                "type": render(source.get("type", "related_to"), row).strip() or "related_to",
                "provenance": provenance,
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
    args = parser.parse_args()
    manifest, base_dir = load_manifest(args.manifest)
    model = build_model(manifest, base_dir)
    payload = json.dumps(model, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
