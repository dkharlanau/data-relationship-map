#!/usr/bin/env python3
"""Directed upstream/downstream lineage traversal for Data Relationship Map."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from typing import Any

from relationship_map import load_model


def _nodes(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(node.get("id")): node for node in model.get("nodes", []) if str(node.get("id", "")).strip()}


def _adjacency(model: dict[str, Any], direction: str) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    nodes = _nodes(model)
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for rel in model.get("relationships", []):
        source = str(rel.get("from", ""))
        target = str(rel.get("to", ""))
        if source not in nodes or target not in nodes:
            continue
        if direction == "downstream":
            adjacency[source].append((target, rel))
        else:
            adjacency[target].append((source, rel))
    for key in adjacency:
        adjacency[key].sort(key=lambda item: (item[0], str(item[1].get("type", ""))))
    return adjacency


def traverse(
    model: dict[str, Any],
    start: str,
    direction: str = "downstream",
    max_depth: int | None = None,
    stop_systems: set[str] | None = None,
    stop_objects: set[str] | None = None,
) -> dict[str, Any]:
    if direction not in {"downstream", "upstream"}:
        raise ValueError("direction must be downstream or upstream")
    if max_depth is not None and max_depth < 0:
        raise ValueError("max_depth must be >= 0")

    nodes = _nodes(model)
    if start not in nodes:
        return {
            "valid_start": False,
            "start": start,
            "direction": direction,
            "reached": [],
            "paths": {},
            "edges": [],
            "boundaries": [],
        }

    stop_systems = stop_systems or set()
    stop_objects = stop_objects or set()
    adjacency = _adjacency(model, direction)
    queue = deque([(start, 0)])
    visited = {start}
    paths: dict[str, list[str]] = {start: [start]}
    edge_keys: set[tuple[str, str, str]] = set()
    edges: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []

    while queue:
        current, depth = queue.popleft()
        current_node = nodes[current]
        if current != start and (
            str(current_node.get("system", "")) in stop_systems
            or str(current_node.get("object", "")) in stop_objects
        ):
            boundaries.append({
                "id": current,
                "system": current_node.get("system"),
                "object": current_node.get("object"),
                "depth": depth,
            })
            continue
        if max_depth is not None and depth >= max_depth:
            continue

        for neighbor, rel in adjacency.get(current, []):
            relation_type = str(rel.get("type", "related_to"))
            if direction == "downstream":
                edge_from, edge_to = current, neighbor
            else:
                edge_from, edge_to = neighbor, current
            key = (edge_from, relation_type, edge_to)
            if key not in edge_keys:
                edges.append({
                    "from": edge_from,
                    "to": edge_to,
                    "type": relation_type,
                    "provenance": rel.get("provenance"),
                })
                edge_keys.add(key)
            if neighbor not in visited:
                visited.add(neighbor)
                paths[neighbor] = paths[current] + [neighbor]
                queue.append((neighbor, depth + 1))

    reached = []
    for node_id in sorted(visited, key=lambda item: (len(paths[item]), item)):
        node = nodes[node_id]
        reached.append({
            "id": node_id,
            "depth": len(paths[node_id]) - 1,
            "system": node.get("system"),
            "object": node.get("object"),
        })

    return {
        "valid_start": True,
        "start": start,
        "direction": direction,
        "reached": reached,
        "paths": {node_id: paths[node_id] for node_id in sorted(paths)},
        "edges": edges,
        "boundaries": sorted(boundaries, key=lambda item: (item["depth"], item["id"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Traverse directed enterprise relationship lineage")
    parser.add_argument("model")
    parser.add_argument("start")
    parser.add_argument("--direction", choices=["downstream", "upstream"], default="downstream")
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--stop-system", action="append", default=[])
    parser.add_argument("--stop-object", action="append", default=[])
    args = parser.parse_args()

    result = traverse(
        load_model(args.model),
        args.start,
        args.direction,
        args.max_depth,
        set(args.stop_system),
        set(args.stop_object),
    )
    print(json.dumps(result, indent=2))
    return 0 if result["valid_start"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
