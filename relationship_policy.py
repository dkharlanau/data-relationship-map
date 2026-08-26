#!/usr/bin/env python3
"""Evaluate relationship graph ambiguity against explicit cardinality policy."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from relationship_map import load_model


def load_policy(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        policy = json.load(handle)
    if not isinstance(policy, dict):
        raise ValueError("policy must be a JSON object")
    return policy


def evaluate(model: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    rules = policy.get("relationship_rules", {})
    by_type_out: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    by_type_in: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for rel in model.get("relationships", []):
        relation = str(rel.get("type", "related_to"))
        source = str(rel.get("from", ""))
        target = str(rel.get("to", ""))
        by_type_out[relation][source].add(target)
        by_type_in[relation][target].add(source)

    violations = []
    for relation in sorted(rules):
        rule = rules[relation]
        max_outgoing = rule.get("max_outgoing")
        max_incoming = rule.get("max_incoming")

        if max_outgoing is not None:
            limit = int(max_outgoing)
            for source, targets in sorted(by_type_out[relation].items()):
                if len(targets) > limit:
                    violations.append({
                        "kind": "outgoing_cardinality",
                        "relationship_type": relation,
                        "node": source,
                        "actual": len(targets),
                        "maximum": limit,
                        "related_ids": sorted(targets),
                    })

        if max_incoming is not None:
            limit = int(max_incoming)
            for target, sources in sorted(by_type_in[relation].items()):
                if len(sources) > limit:
                    violations.append({
                        "kind": "incoming_cardinality",
                        "relationship_type": relation,
                        "node": target,
                        "actual": len(sources),
                        "maximum": limit,
                        "related_ids": sorted(sources),
                    })

    identity_collisions = []
    if policy.get("report_identity_collisions", True):
        for node in model.get("nodes", []):
            collisions = sorted({str(value) for value in node.get("identity_collisions", []) if str(value)})
            if collisions:
                identity_collisions.append({"node": str(node.get("id", "")), "raw_identities": collisions})

    fail_on_collisions = bool(policy.get("fail_on_identity_collisions", True))
    passed = not violations and (not fail_on_collisions or not identity_collisions)
    return {
        "passed": passed,
        "cardinality_violations": violations,
        "identity_collisions": identity_collisions,
        "failed_checks": [
            *( ["relationship_cardinality"] if violations else [] ),
            *( ["identity_collisions"] if fail_on_collisions and identity_collisions else [] ),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate relationship graph cardinality and ambiguity")
    parser.add_argument("model")
    parser.add_argument("policy")
    args = parser.parse_args()
    result = evaluate(load_model(args.model), load_policy(args.policy))
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
