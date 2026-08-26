#!/usr/bin/env python3
"""Build a canonical relationship graph from CSV exports using a small JSON manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterator


def render(template: str, row: dict[str, str]) -> str:
    try:
        return template.format_map(row)
    except KeyError as exc:
        raise ValueError(f"missing CSV column {exc.args[0]!r} required by template {template!r}") from exc


def read_rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            yield row_number, dict(row)


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


def build_model(manifest: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []

    for source in manifest.get("node_sources", []):
        for row_number, row in read_rows(base_dir / source["file"]):
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
            _merge_node(nodes, node, {"file": source["file"], "row": row_number})

    for source in manifest.get("relationship_sources", []):
        for row_number, row in read_rows(base_dir / source["file"]):
            from_id = render(source["from"], row).strip()
            to_id = render(source["to"], row).strip()
            if not from_id or not to_id:
                continue
            relationships.append({
                "from": from_id,
                "to": to_id,
                "type": render(source.get("type", "related_to"), row).strip() or "related_to",
                "provenance": {"file": source["file"], "row": row_number},
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
