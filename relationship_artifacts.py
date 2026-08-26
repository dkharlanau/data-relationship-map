#!/usr/bin/env python3
"""Emit stable Enterprise-as-Code artifacts from Data Relationship Map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from relationship_map import analyze, load_model
from relationship_policy import evaluate as evaluate_policy
from relationship_policy import load_policy


def artifact_ref(kind: str, *segments: str) -> str:
    encoded = "/".join(quote(str(segment), safe="._-:@") for segment in segments)
    return f"eac://dkharlanau/data-relationship-map/{quote(kind, safe='._-')}/{encoded}"


def build_index(model: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    validation = analyze(model)
    node_refs: dict[str, str] = {}
    objects = []
    for node in sorted(model.get("nodes", []), key=lambda item: str(item.get("id", ""))):
        node_id = str(node.get("id", "")).strip()
        if not node_id:
            continue
        ref = artifact_ref("object", node_id)
        node_refs[node_id] = ref
        artifact: dict[str, Any] = {
            "id": node_id,
            "artifact_ref": ref,
            "system": node.get("system"),
            "object": node.get("object"),
        }
        for field in ("label", "provenance", "conflicts", "identity_collisions"):
            if node.get(field) is not None:
                artifact[field] = node[field]
        objects.append(artifact)

    relationships = []
    for relation in sorted(
        model.get("relationships", []),
        key=lambda item: (
            str(item.get("from", "")),
            str(item.get("type", "related_to")),
            str(item.get("to", "")),
        ),
    ):
        source = str(relation.get("from", "")).strip()
        target = str(relation.get("to", "")).strip()
        relation_type = str(relation.get("type", "related_to")).strip() or "related_to"
        if not source or not target:
            continue
        artifact: dict[str, Any] = {
            "artifact_ref": artifact_ref("relationship", source, relation_type, target),
            "from": source,
            "to": target,
            "from_ref": node_refs.get(source),
            "to_ref": node_refs.get(target),
            "type": relation_type,
        }
        if relation.get("provenance") is not None:
            artifact["provenance"] = relation["provenance"]
        relationships.append(artifact)

    policy_result = evaluate_policy(model, policy) if policy is not None else None
    findings = []
    if policy_result is not None:
        for violation in policy_result.get("violations", []):
            finding_ref = artifact_ref(
                "finding",
                "cardinality",
                str(violation.get("relationship_type", "related_to")),
                str(violation.get("direction", "unknown")),
                str(violation.get("node", "unknown")),
            )
            findings.append({
                "artifact_ref": finding_ref,
                "kind": "cardinality",
                "severity": "error",
                "node": violation.get("node"),
                "node_ref": node_refs.get(str(violation.get("node", ""))),
                "relationship_type": violation.get("relationship_type"),
                "direction": violation.get("direction"),
                "actual": violation.get("actual"),
                "allowed": violation.get("allowed"),
                "related": violation.get("related", []),
            })
        for collision in policy_result.get("identity_collisions", []):
            node_id = str(collision.get("node", ""))
            findings.append({
                "artifact_ref": artifact_ref("finding", "identity-collision", node_id),
                "kind": "identity_collision",
                "severity": "error" if policy.get("fail_on_identity_collisions", False) else "warning",
                "node": node_id,
                "node_ref": node_refs.get(node_id),
                "raw_identities": collision.get("raw_identities", []),
                "provenance": collision.get("provenance", []),
            })

    findings.sort(key=lambda item: item["artifact_ref"])
    return {
        "schema_version": "0.1",
        "repository": "dkharlanau/data-relationship-map",
        "valid": bool(validation["valid"]),
        "validation": validation,
        "policy_evaluated": policy_result is not None,
        "policy_passed": policy_result["passed"] if policy_result is not None else None,
        "objects": objects,
        "relationships": relationships,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit stable eac:// artifacts from Data Relationship Map")
    parser.add_argument("model")
    parser.add_argument("--policy")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()

    index = build_index(load_model(args.model), load_policy(args.policy) if args.policy else None)
    payload = json.dumps(index, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if index["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
