#!/usr/bin/env python3
"""Build a canonical relationship graph from CSV exports using a small JSON manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterator

from import_report import ImportReport, ImportRecordError, validate_output_paths, write_report, write_text_atomic, IMPORT_ERRORS


def render(template: str, row: dict[str, str]) -> str:
    try:
        return template.format_map(row)
    except KeyError as exc:
        raise ImportRecordError(f"missing CSV column {exc.args[0]!r} required by template {template!r}", "missing_template_column") from exc


def required_identity_columns(source: dict[str, Any], location: str = "Source") -> tuple[str, ...]:
    """Read an explicit source contract; never infer business keys from a template."""
    columns = source.get("required_identity_columns", [])
    if not isinstance(columns, list) or any(not isinstance(name, str) or not name.strip() for name in columns):
        raise ValueError(f"{location}: required_identity_columns must be a list of non-empty column names")
    if len(columns) != len(set(columns)):
        raise ValueError(f"{location}: required_identity_columns contains duplicate column names")
    return tuple(columns)


def check_identity_headers(headers: list[str], columns: tuple[str, ...], location: str) -> None:
    missing = [name for name in columns if name not in headers]
    if missing:
        raise ValueError(f"{location}: required identity columns missing from header: {missing!r}")


def check_identity_values(row: dict[str, str], columns: tuple[str, ...], location: str) -> None:
    missing = [name for name in columns if not row[name].strip()]
    if missing:
        raise ImportRecordError(f"{location}: required identity columns are blank: {missing!r}", "blank_identity_component")


def read_rows(path: Path, *, required_columns: tuple[str, ...] = (), report: ImportReport | None = None) -> Iterator[tuple[int, dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            headers = next(reader, [])
            if not headers:
                raise ValueError(f"CSV has no header: {path}")
            if any(not name.strip() for name in headers):
                raise ValueError(f"CSV header contains an empty column name: {path}")
            if len(headers) != len(set(headers)):
                raise ValueError(f"CSV header contains duplicate column names: {path}")
            check_identity_headers(headers, required_columns, f"CSV {path.name!r}")
            while True:
                row_number = reader.line_num + 1
                values = next(reader, None)
                if values is None:
                    break
                if report is not None:
                    report.row(row_number, reader.line_num)
                if not values:
                    if report is not None:
                        report.record("skipped", "blank_record")
                    continue
                if len(values) != len(headers):
                    raise ValueError(f"CSV row at line {row_number} does not match the header width: {path}")
                yield row_number, dict(zip(headers, values))
    except csv.Error as exc:
        if report is not None and "row_number" in locals():
            report.row(row_number, reader.line_num)
        raise ValueError(f"Invalid CSV at line {reader.line_num}: {path}: {exc}") from exc


def _merge_node(nodes: dict[str, dict[str, Any]], candidate: dict[str, Any], source_ref: dict[str, Any]) -> None:
    node_id = candidate["id"]
    if node_id not in nodes:
        candidate["provenance"] = [source_ref]
        nodes[node_id] = candidate
        return

    node = nodes[node_id]
    node.setdefault("provenance", []).append(source_ref)

    raw_identities = {
        str(ref.get("raw_identity") or node_id)
        for ref in node.get("provenance", [])
    }
    if len(raw_identities) > 1:
        node["identity_collisions"] = sorted(raw_identities)

    conflicts = node.setdefault("conflicts", {})
    for field in ("system", "object", "label"):
        old = str(node.get(field, "")).strip()
        new = str(candidate.get(field, "")).strip()
        if not new:
            continue
        if not old:
            node[field] = new
        elif old != new:
            values = set(conflicts.get(field, [])) | {old, new}
            conflicts[field] = sorted(values)
    if not conflicts:
        node.pop("conflicts", None)


def build_model(manifest: dict[str, Any], base_dir: Path, *, import_report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = ImportReport(import_report, "csv", manifest)
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
        columns = required_identity_columns(source, f"CSV {source['file']!r}")
        for row_number, row in read_rows(base_dir / source["file"], required_columns=columns, report=report):
            if not any(value.strip() for value in row.values()):
                report.record("skipped", "blank_record")
                continue
            check_identity_values(row, columns, f"CSV {source['file']!r}, line {row_number}")
            node_id = render(source["id"], row).strip()
            if not node_id:
                raise ImportRecordError(f"CSV {source['file']!r}, line {row_number}" + ": node id renders empty", "blank_node_id")
            node: dict[str, Any] = {
                "id": node_id,
                "system": render(source.get("system", ""), row).strip(),
                "object": render(source.get("object", ""), row).strip(),
            }
            if source.get("label"):
                node["label"] = render(source["label"], row).strip()
            disposition = "node_merged" if node_id in nodes else "node_created"
            _merge_node(nodes, node, {"file": source["file"], "row": row_number})
            report.record("accepted", disposition, {"kind": "node", "id": node_id})

    for source_index, source in enumerate(manifest.get("relationship_sources", [])):
        report.source("relationship_sources", source_index)
        columns = required_identity_columns(source, f"CSV {source['file']!r}")
        for row_number, row in read_rows(base_dir / source["file"], required_columns=columns, report=report):
            if not any(value.strip() for value in row.values()):
                report.record("skipped", "blank_record")
                continue
            check_identity_values(row, columns, f"CSV {source['file']!r}, line {row_number}")
            from_id = render(source["from"], row).strip()
            to_id = render(source["to"], row).strip()
            if not from_id or not to_id:
                missing = ", ".join(field for field, value in (("from", from_id), ("to", to_id)) if not value)
                raise ImportRecordError(f"CSV {source['file']!r}, line {row_number}" + f": relationship {missing} renders empty", "blank_relationship_endpoint")
            relationships.append({
                "from": from_id,
                "to": to_id,
                "type": render(source.get("type", "related_to"), row).strip() or "related_to",
                "provenance": {"file": source["file"], "row": row_number},
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
    parser = argparse.ArgumentParser(description="Convert CSV exports into a Data Relationship Map model")
    parser.add_argument("manifest", help="Path to adapter manifest JSON")
    parser.add_argument("--output", "-o", help="Write canonical JSON to this path")
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
