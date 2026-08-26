#!/usr/bin/env python3
"""Git-native cross-system relationship analysis with zero runtime dependencies."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


def load_model(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        model = json.load(handle)
    if not isinstance(model, dict):
        raise ValueError("model must be a JSON object")
    return model


def analyze(model: dict[str, Any]) -> dict[str, Any]:
    nodes = model.get("nodes", [])
    relationships = model.get("relationships", [])

    ids = [str(node.get("id", "")) for node in nodes]
    known = {node_id for node_id in ids if node_id}
    counts: dict[str, int] = defaultdict(int)
    for node_id in ids:
        counts[node_id] += 1
    duplicate_nodes = sorted(node_id for node_id, count in counts.items() if node_id and count > 1)

    broken = []
    duplicate_relationships = []
    seen_relationships: set[tuple[str, str, str]] = set()
    degree: dict[str, int] = defaultdict(int)

    for index, rel in enumerate(relationships):
        source = str(rel.get("from", ""))
        target = str(rel.get("to", ""))
        relation = str(rel.get("type", "related_to"))
        key = (source, relation, target)

        if key in seen_relationships:
            duplicate_relationships.append({"index": index, "from": source, "type": relation, "to": target})
        seen_relationships.add(key)

        missing = [node_id for node_id in (source, target) if node_id not in known]
        if missing:
            broken.append({"index": index, "from": source, "type": relation, "to": target, "missing": missing})
        else:
            degree[source] += 1
            degree[target] += 1

    orphans = sorted(node_id for node_id in known if degree[node_id] == 0)
    return {
        "node_count": len(nodes),
        "relationship_count": len(relationships),
        "duplicate_nodes": duplicate_nodes,
        "duplicate_relationships": duplicate_relationships,
        "broken_relationships": broken,
        "orphans": orphans,
        "valid": not duplicate_nodes and not duplicate_relationships and not broken,
    }


def shortest_path(model: dict[str, Any], start: str, end: str) -> list[str]:
    graph: dict[str, list[str]] = defaultdict(list)
    known = {str(node.get("id", "")) for node in model.get("nodes", [])}
    if start not in known or end not in known:
        return []

    for rel in model.get("relationships", []):
        source = str(rel.get("from", ""))
        target = str(rel.get("to", ""))
        if source in known and target in known:
            graph[source].append(target)
            graph[target].append(source)

    queue = deque([(start, [start])])
    visited = {start}
    while queue:
        current, path = queue.popleft()
        if current == end:
            return path
        for neighbor in graph[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze cross-system enterprise object relationships")
    parser.add_argument("model", help="Path to relationship model JSON")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("validate")
    path_parser = sub.add_parser("path")
    path_parser.add_argument("from_id")
    path_parser.add_argument("to_id")
    args = parser.parse_args()

    model = load_model(args.model)
    if args.command == "path":
        path = shortest_path(model, args.from_id, args.to_id)
        print(" -> ".join(path) if path else "NO_PATH")
        return 0 if path else 2

    result = analyze(model)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
