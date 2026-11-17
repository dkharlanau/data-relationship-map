#!/usr/bin/env python3
"""Evaluate relationship graph ambiguity against explicit cardinality policy."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from relationship_map import load_model


class PolicyValidationError(ValueError):
    """An invalid supplied policy, never an evaluated graph finding."""


def validate_policy(policy: Any) -> None:
    """Validate explicit configuration without coercion or changing its semantics."""
    if not isinstance(policy, dict):
        raise PolicyValidationError("policy must be a JSON object")
    if set(policy) - {"relationship_rules", "report_identity_collisions", "fail_on_identity_collisions"}:
        raise PolicyValidationError("policy contains unsupported fields")
    for flag in ("report_identity_collisions", "fail_on_identity_collisions"):
        if flag in policy and type(policy[flag]) is not bool:
            raise PolicyValidationError("policy collision flags must be booleans")
    rules = policy.get("relationship_rules", {})
    if not isinstance(rules, dict):
        raise PolicyValidationError("policy relationship_rules must be an object")
    for relation, rule in rules.items():
        if not isinstance(relation, str) or not relation.strip():
            raise PolicyValidationError("policy relationship types must be nonblank strings")
        if not isinstance(rule, dict):
            raise PolicyValidationError("policy relationship rules must be objects")
        if set(rule) - {"max_outgoing", "max_incoming"}:
            raise PolicyValidationError("policy relationship rule contains unsupported fields")
        for key in ("max_outgoing", "max_incoming"):
            value = rule.get(key)
            if value is not None and (type(value) is not int or value < 0):
                raise PolicyValidationError("policy cardinality limits must be nonnegative integers or null")


def load_policy(path: str | Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                raise PolicyValidationError("policy JSON contains repeated members")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise PolicyValidationError("policy JSON must contain finite numbers")

    def finite_float(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise PolicyValidationError("policy JSON must contain finite numbers")
        return number

    try:
        with open(path, "r", encoding="utf-8") as handle:
            policy = json.load(handle, object_pairs_hook=pairs,
                               parse_constant=reject_constant, parse_float=finite_float)
    except PolicyValidationError:
        raise
    except (OSError, ValueError, RecursionError):
        raise PolicyValidationError("policy cannot be read as unambiguous UTF-8 JSON") from None
    validate_policy(policy)
    return policy


def evaluate(model: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    validate_policy(policy)
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
            limit = max_outgoing
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
            limit = max_incoming
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
    try:
        result = evaluate(load_model(args.model), load_policy(args.policy))
    except PolicyValidationError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
