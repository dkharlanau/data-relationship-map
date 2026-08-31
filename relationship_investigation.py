#!/usr/bin/env python3
"""Build one deterministic relationship investigation report from existing analyzers."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from relationship_lineage import traverse
from relationship_map import analyze, load_model
from relationship_policy import evaluate, load_policy

SCHEMA_VERSION = "0.1"


def _node_by_id(model: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in model.get("nodes", []):
        if str(node.get("id", "")) == node_id:
            return node
    return None


def _as_provenance_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _source_references(
    focus_node: dict[str, Any] | None,
    upstream: dict[str, Any] | None,
    downstream: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(kind: str, owner: str, provenance: Any) -> None:
        for item in _as_provenance_items(provenance):
            canonical = json.dumps(item, sort_keys=True, separators=(",", ":"), default=str)
            key = f"{kind}|{owner}|{canonical}"
            if key in seen:
                continue
            seen.add(key)
            refs.append({"kind": kind, "owner": owner, "provenance": item})

    if focus_node is not None:
        add("node", str(focus_node.get("id", "")), focus_node.get("provenance"))

    for direction, result in (("upstream", upstream), ("downstream", downstream)):
        if not result:
            continue
        for edge in result.get("edges", []):
            owner = f"{edge.get('from', '')}->{edge.get('to', '')}:{edge.get('type', 'related_to')}"
            add(f"{direction}_relationship", owner, edge.get("provenance"))

    return sorted(
        refs,
        key=lambda item: (
            item["kind"],
            item["owner"],
            json.dumps(item["provenance"], sort_keys=True, default=str),
        ),
    )


def build_investigation(
    model: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    focus: str | None = None,
    max_depth: int | None = 2,
    stop_systems: set[str] | None = None,
    stop_objects: set[str] | None = None,
) -> dict[str, Any]:
    structural = analyze(model)
    policy_result = evaluate(model, policy) if policy is not None else None

    structural_finding_count = (
        len(structural.get("duplicate_nodes", []))
        + len(structural.get("duplicate_relationships", []))
        + len(structural.get("broken_relationships", []))
        + len(structural.get("orphans", []))
    )
    policy_finding_count = 0
    if policy_result is not None:
        policy_finding_count = (
            len(policy_result.get("cardinality_violations", []))
            + len(policy_result.get("identity_collisions", []))
        )

    focus_node = _node_by_id(model, focus) if focus else None
    if focus and focus_node is None:
        status = "invalid_focus"
        upstream = None
        downstream = None
    else:
        upstream = (
            traverse(
                model,
                focus,
                direction="upstream",
                max_depth=max_depth,
                stop_systems=stop_systems,
                stop_objects=stop_objects,
            )
            if focus
            else None
        )
        downstream = (
            traverse(
                model,
                focus,
                direction="downstream",
                max_depth=max_depth,
                stop_systems=stop_systems,
                stop_objects=stop_objects,
            )
            if focus
            else None
        )
        if not structural["valid"]:
            status = "invalid_model"
        elif structural_finding_count or policy_finding_count:
            status = "findings"
        else:
            status = "clear"

    focus_summary = None
    if focus:
        focus_summary = {
            "id": focus,
            "valid": focus_node is not None,
            "node": focus_node,
            "upstream": upstream,
            "downstream": downstream,
            "source_references": _source_references(focus_node, upstream, downstream),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "summary": {
            "node_count": structural["node_count"],
            "relationship_count": structural["relationship_count"],
            "structural_finding_count": structural_finding_count,
            "policy_finding_count": policy_finding_count,
            "focus": focus,
            "max_depth": max_depth,
            "stop_systems": sorted(stop_systems or set()),
            "stop_objects": sorted(stop_objects or set()),
        },
        "structural": structural,
        "policy": policy_result,
        "focus": focus_summary,
    }


def _bullet_findings(report: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    structural = report["structural"]
    for node_id in structural.get("duplicate_nodes", []):
        lines.append(f"- Duplicate node: `{node_id}`")
    for item in structural.get("duplicate_relationships", []):
        lines.append(
            f"- Duplicate relationship: `{item.get('from')}` → `{item.get('to')}` ({item.get('type')})"
        )
    for item in structural.get("broken_relationships", []):
        missing = ", ".join(f"`{value}`" for value in item.get("missing", []))
        lines.append(
            f"- Broken relationship: `{item.get('from')}` → `{item.get('to')}` ({item.get('type')}); missing {missing}"
        )
    for node_id in structural.get("orphans", []):
        lines.append(f"- Orphan node: `{node_id}`")

    policy = report.get("policy") or {}
    for item in policy.get("cardinality_violations", []):
        related = ", ".join(f"`{value}`" for value in item.get("related_ids", []))
        lines.append(
            f"- Cardinality violation ({item.get('relationship_type')} / {item.get('kind')}): "
            f"`{item.get('node')}` has {item.get('actual')} relationships, maximum {item.get('maximum')}; related {related}"
        )
    for item in policy.get("identity_collisions", []):
        raw = ", ".join(f"`{value}`" for value in item.get("raw_identities", []))
        lines.append(f"- Identity collision: `{item.get('node')}` represents raw identities {raw}")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Data Relationship Investigation",
        "",
        f"**Status:** `{report['status']}`",
        "",
        "## Graph summary",
        "",
        f"- Nodes: **{summary['node_count']}**",
        f"- Relationships: **{summary['relationship_count']}**",
        f"- Structural findings: **{summary['structural_finding_count']}**",
        f"- Policy findings: **{summary['policy_finding_count']}**",
    ]

    findings = _bullet_findings(report)
    lines += ["", "## Findings", ""]
    lines += findings or ["No structural or supplied-policy findings."]

    focus = report.get("focus")
    if focus:
        lines += ["", "## Focus", "", f"**Object:** `{focus['id']}`"]
        if not focus["valid"]:
            lines += ["", "The focus object does not exist in the supplied model."]
        else:
            node = focus.get("node") or {}
            lines += [
                "",
                f"- System: `{node.get('system', '')}`",
                f"- Object type: `{node.get('object', '')}`",
            ]
            for direction in ("upstream", "downstream"):
                traversal = focus.get(direction) or {}
                reached = traversal.get("reached", [])
                boundaries = traversal.get("boundaries", [])
                lines += [
                    "",
                    f"### {direction.title()} context",
                    "",
                    f"Reached **{max(len(reached) - 1, 0)}** related objects within the configured boundary.",
                ]
                if boundaries:
                    lines.append(f"Stopped at **{len(boundaries)}** explicit traversal boundaries.")

            refs = focus.get("source_references", [])
            lines += ["", "### Source references", ""]
            if refs:
                for ref in refs:
                    provenance = json.dumps(ref["provenance"], sort_keys=True, ensure_ascii=False)
                    lines.append(f"- `{ref['kind']}` `{ref['owner']}` — `{provenance}`")
            else:
                lines.append("No provenance is attached to the focus object or traversed relationships.")

    lines += [
        "",
        "## Interpretation boundary",
        "",
        "This report consolidates deterministic structural analysis, explicit relationship policy, directional lineage, and retained provenance. It does not infer business meaning or invent links that are absent from the supplied model.",
        "",
    ]
    return "\n".join(lines)


def render_html(report: dict[str, Any]) -> str:
    """Render the same deterministic report as a portable browser document."""
    title = "Data Relationship Investigation"
    status = str(report.get("status", "unknown"))
    markdown = render_markdown(report)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{html.escape(title)} — {html.escape(status)}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: Canvas; color: CanvasText; }}
    main {{ width: min(960px, calc(100% - 32px)); margin: 40px auto; }}
    .eyebrow {{ color: #64748b; font-size: .78rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
    h1 {{ margin: .4rem 0 1rem; font-size: clamp(2rem, 5vw, 3.6rem); letter-spacing: -.045em; }}
    .status {{ display: inline-block; padding: .45rem .75rem; border: 1px solid currentColor; border-radius: 999px; font-weight: 700; }}
    pre {{ margin: 2rem 0 0; padding: clamp(1rem, 3vw, 2rem); overflow: auto; border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: 16px; background: color-mix(in srgb, CanvasText 4%, Canvas); white-space: pre-wrap; word-break: break-word; font: .9rem/1.65 ui-monospace, SFMono-Regular, Menlo, monospace; }}
  </style>
</head>
<body>
  <main>
    <div class=\"eyebrow\">Synthetic, deterministic investigation output</div>
    <h1>{html.escape(title)}</h1>
    <div class=\"status\">{html.escape(status)}</div>
    <pre>{html.escape(markdown)}</pre>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a consolidated relationship investigation report")
    parser.add_argument("model")
    parser.add_argument("--policy")
    parser.add_argument("--focus")
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--stop-system", action="append", default=[])
    parser.add_argument("--stop-object", action="append", default=[])
    parser.add_argument("--json-output")
    parser.add_argument("--markdown")
    parser.add_argument("--html")
    args = parser.parse_args()

    report = build_investigation(
        load_model(args.model),
        policy=load_policy(args.policy) if args.policy else None,
        focus=args.focus,
        max_depth=args.max_depth,
        stop_systems=set(args.stop_system),
        stop_objects=set(args.stop_object),
    )

    if args.json_output:
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(render_markdown(report), encoding="utf-8")
    if args.html:
        Path(args.html).parent.mkdir(parents=True, exist_ok=True)
        Path(args.html).write_text(render_html(report), encoding="utf-8")
    if not args.json_output and not args.markdown and not args.html:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    if report["status"] == "invalid_focus":
        return 2
    return 0 if report["status"] == "clear" else 1


if __name__ == "__main__":
    raise SystemExit(main())
