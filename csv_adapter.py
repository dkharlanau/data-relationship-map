#!/usr/bin/env python3
"""Build a canonical relationship graph from CSV exports using a small JSON manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def render(template: str, row: dict[str, str]) -> str:
    try:
        return template.format_map(row)
    except KeyError as exc:
        raise ValueError(f"missing CSV column {exc.args[0]!r} required by template {template!r}") from exc


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def build_model(manifest: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, str]] = []

    for source in manifest.get("node_sources", []):
        rows = read_rows(base_dir / source["file"])
        for row in rows:
            node_id = render(source["id"], row).strip()
            if not node_id:
                continue
            node = {
                "id": node_id,
                "system": render(source.get("system", ""), row).strip(),
                "object": render(source.get("object", ""), row).strip(),
            }
            if source.get("label"):
                node["label"] = render(source["label"], row).strip()
            nodes[node_id] = node

    for source in manifest.get("relationship_sources", []):
        rows = read_rows(base_dir / source["file"])
        for row in rows:
            from_id = render(source["from"], row).strip()
            to_id = render(source["to"], row).strip()
            if not from_id or not to_id:
                continue
            relationships.append({
                "from": from_id,
                "to": to_id,
                "type": render(source.get("type", "related_to"), row).strip() or "related_to",
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
