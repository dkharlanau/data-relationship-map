#!/usr/bin/env python3
"""Compare two relationship graph snapshots and surface identity/linkage drift."""

from __future__ import annotations

import argparse
import json
from typing import Any

from relationship_map import analyze, load_model


def _node_map(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(node.get("id")): node for node in model.get("nodes", []) if node.get("id")}


def _relationship_set(model: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (str(rel.get("from", "")), str(rel.get("type", "related_to")), str(rel.get("to", "")))
        for rel in model.get("relationships", [])
    }


def _stable_node_fields(node: dict[str, Any]) -> dict[str, Any]:
    return {key: node.get(key) for key in ("system", "object", "label") if key in node}


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_nodes = _node_map(before)
    after_nodes = _node_map(after)
    before_ids = set(before_nodes)
    after_ids = set(after_nodes)

    changed_nodes = []
    for node_id in sorted(before_ids & after_ids):
        old = _stable_node_fields(before_nodes[node_id])
        new = _stable_node_fields(after_nodes[node_id])
        if old != new:
            changed_nodes.append({"id": node_id, "before": old, "after": new})

    before_rel = _relationship_set(before)
    after_rel = _relationship_set(after)
    before_analysis = analyze(before)
    after_analysis = analyze(after)
    before_orphans = set(before_analysis["orphans"])
    after_orphans = set(after_analysis["orphans"])

    def rel(item: tuple[str, str, str]) -> dict[str, str]:
        source, relation, target = item
        return {"from": source, "type": relation, "to": target}

    return {
        "added_nodes": sorted(after_ids - before_ids),
        "removed_nodes": sorted(before_ids - after_ids),
        "changed_nodes": changed_nodes,
        "added_relationships": [rel(item) for item in sorted(after_rel - before_rel)],
        "removed_relationships": [rel(item) for item in sorted(before_rel - after_rel)],
        "new_orphans": sorted(after_orphans - before_orphans),
        "resolved_orphans": sorted(before_orphans - after_orphans),
        "validation": {
            "before_valid": before_analysis["valid"],
            "after_valid": after_analysis["valid"],
            "broken_before": before_analysis["broken_relationships"],
            "broken_after": after_analysis["broken_relationships"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two Data Relationship Map snapshots")
    parser.add_argument("before")
    parser.add_argument("after")
    args = parser.parse_args()
    print(json.dumps(compare(load_model(args.before), load_model(args.after)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
