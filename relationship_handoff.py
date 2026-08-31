#!/usr/bin/env python3
"""Build and verify bounded, integrity-checkable relationship handoff packs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from relationship_artifacts import build_index, normalize_observed_at
from relationship_investigation import build_investigation, render_html, render_markdown
from relationship_map import load_model
from relationship_policy import load_policy


SCHEMA_VERSION = "0.2"
LEGACY_PACK_FILES = ("graph.json", "investigation.json", "investigation.md", "investigation.html")
PACK_FILES = (*LEGACY_PACK_FILES, "artifact-index.json")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bounded_graph(model: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    focus = report.get("focus")
    if not isinstance(focus, dict) or not focus.get("valid"):
        raise ValueError("a valid --focus object is required for a bounded handoff")

    selected = {str(focus["id"])}
    for direction in ("upstream", "downstream"):
        traversal = focus.get(direction) or {}
        selected.update(str(item["id"]) for item in traversal.get("reached", []))

    graph = {
        key: value
        for key, value in model.items()
        if key not in {"nodes", "relationships"}
    }
    graph["nodes"] = sorted(
        [node for node in model.get("nodes", []) if str(node.get("id", "")) in selected],
        key=lambda item: str(item.get("id", "")),
    )
    graph["relationships"] = sorted(
        [
            relationship
            for relationship in model.get("relationships", [])
            if str(relationship.get("from", "")) in selected
            and str(relationship.get("to", "")) in selected
        ],
        key=lambda item: (
            str(item.get("from", "")),
            str(item.get("type", "")),
            str(item.get("to", "")),
            json.dumps(item, sort_keys=True, default=str),
        ),
    )
    return graph


def build_handoff(
    model: dict[str, Any],
    output_dir: str | Path,
    *,
    focus: str,
    policy: dict[str, Any] | None = None,
    max_depth: int | None = 2,
    stop_systems: set[str] | None = None,
    stop_objects: set[str] | None = None,
    observed_at: Any = None,
) -> dict[str, Any]:
    scoped_model = dict(model)
    observation = normalize_observed_at(observed_at if observed_at is not None else model.get("observed_at"))
    if observation is not None:
        scoped_model["observed_at"] = observation

    scope_report = build_investigation(
        scoped_model,
        policy=policy,
        focus=focus,
        max_depth=max_depth,
        stop_systems=stop_systems,
        stop_objects=stop_objects,
    )
    if scope_report["status"] in {"invalid_model", "invalid_focus"}:
        raise ValueError(f"cannot build handoff from {scope_report['status']}")

    graph = _bounded_graph(scoped_model, scope_report)
    # Re-evaluate the selected graph so every finding in the handoff can be
    # reconstructed from the files inside the handoff itself.
    report = build_investigation(
        graph,
        policy=policy,
        focus=focus,
        max_depth=max_depth,
        stop_systems=stop_systems,
        stop_objects=stop_objects,
    )
    artifact_index = build_index(graph, policy)
    semantic_payload = {"graph": graph, "investigation": report, "artifact_index": artifact_index}
    pack_id = "relationship-handoff-" + hashlib.sha256(_canonical_bytes(semantic_payload)).hexdigest()[:24]

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "graph.json").write_text(
        json.dumps(graph, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (destination / "investigation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (destination / "investigation.md").write_text(render_markdown(report), encoding="utf-8")
    (destination / "investigation.html").write_text(render_html(report), encoding="utf-8")
    (destination / "artifact-index.json").write_text(
        json.dumps(artifact_index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    files = {
        name: {
            "sha256": _sha256(destination / name),
            "bytes": (destination / name).stat().st_size,
        }
        for name in PACK_FILES
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "pack_id": pack_id,
        "purpose": "bounded-cross-system-relationship-investigation-handoff",
        "focus": focus,
        "status": report["status"],
        "observed_at": artifact_index.get("observed_at"),
        "bounds": {
            "max_depth": max_depth,
            "stop_systems": sorted(stop_systems or set()),
            "stop_objects": sorted(stop_objects or set()),
        },
        "summary": {
            "nodes": len(graph["nodes"]),
            "relationships": len(graph["relationships"]),
            "structural_findings": report["summary"]["structural_finding_count"],
            "policy_findings": report["summary"]["policy_finding_count"],
        },
        "files": files,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_handoff(output_dir: str | Path) -> dict[str, Any]:
    destination = Path(output_dir)
    errors: list[dict[str, Any]] = []
    try:
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "pack_id": None, "errors": [{"kind": "invalid_manifest", "detail": str(exc)}]}

    schema_version = str(manifest.get("schema_version", "0.1"))
    if schema_version == "0.2":
        pack_files = PACK_FILES
    elif schema_version == "0.1":
        pack_files = LEGACY_PACK_FILES
    else:
        return {
            "valid": False,
            "pack_id": manifest.get("pack_id"),
            "errors": [{"kind": "unsupported_schema_version", "schema_version": schema_version}],
        }

    for name in pack_files:
        path = destination / name
        expected = (manifest.get("files") or {}).get(name)
        if not isinstance(expected, dict):
            errors.append({"kind": "missing_manifest_entry", "file": name})
            continue
        if not path.is_file():
            errors.append({"kind": "missing_file", "file": name})
            continue
        actual_hash = _sha256(path)
        if actual_hash != expected.get("sha256"):
            errors.append({"kind": "sha256_mismatch", "file": name})
        if path.stat().st_size != expected.get("bytes"):
            errors.append({"kind": "size_mismatch", "file": name})

    if not errors:
        try:
            graph = json.loads((destination / "graph.json").read_text(encoding="utf-8"))
            investigation = json.loads((destination / "investigation.json").read_text(encoding="utf-8"))
            semantic_payload = {"graph": graph, "investigation": investigation}
            if schema_version == "0.2":
                semantic_payload["artifact_index"] = json.loads(
                    (destination / "artifact-index.json").read_text(encoding="utf-8")
                )
            expected_id = "relationship-handoff-" + hashlib.sha256(
                _canonical_bytes(semantic_payload)
            ).hexdigest()[:24]
            if manifest.get("pack_id") != expected_id:
                errors.append({"kind": "pack_id_mismatch", "expected": expected_id})
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"kind": "invalid_payload", "detail": str(exc)})

    return {
        "valid": not errors,
        "pack_id": manifest.get("pack_id"),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify a bounded relationship handoff")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("model")
    build_parser.add_argument("output_dir")
    build_parser.add_argument("--focus", required=True)
    build_parser.add_argument("--policy")
    build_parser.add_argument("--max-depth", type=int, default=2)
    build_parser.add_argument("--stop-system", action="append", default=[])
    build_parser.add_argument("--stop-object", action="append", default=[])
    build_parser.add_argument(
        "--observed-at",
        help="explicit ISO-8601 time when the supplied exports/model were observed; must include timezone",
    )

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("output_dir")
    args = parser.parse_args()

    try:
        if args.command == "build":
            result = build_handoff(
                load_model(args.model),
                args.output_dir,
                focus=args.focus,
                policy=load_policy(args.policy) if args.policy else None,
                max_depth=args.max_depth,
                stop_systems=set(args.stop_system),
                stop_objects=set(args.stop_object),
                observed_at=args.observed_at,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        result = verify_handoff(args.output_dir)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["valid"] else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"relationship handoff: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
