#!/usr/bin/env python3
"""Unified command dispatcher for Data Relationship Map."""

from __future__ import annotations

import sys
from collections.abc import Callable

import csv_adapter
import relationship_artifacts
import relationship_diff
import relationship_lineage
import relationship_map
import relationship_policy
import xlsx_adapter


Main = Callable[[], int]


COMMANDS: dict[str, tuple[Main, str]] = {
    "lineage": (relationship_lineage.main, "Trace strict upstream/downstream lineage"),
    "policy": (relationship_policy.main, "Evaluate identity/cardinality policy"),
    "diff": (relationship_diff.main, "Compare relationship graph snapshots"),
    "artifacts": (relationship_artifacts.main, "Emit stable eac:// objects, relationships and findings"),
    "import-csv": (csv_adapter.main, "Build a canonical graph from CSV exports"),
    "import-xlsx": (xlsx_adapter.main, "Build a canonical graph from XLSX exports"),
}


def _usage() -> str:
    rows = [
        "Data Relationship Map — cross-system identity and lineage investigations",
        "",
        "Usage:",
        "  data-relationship-map validate MODEL",
        "  data-relationship-map path MODEL FROM_ID TO_ID",
        "  data-relationship-map COMMAND [ARGS...]",
        "",
        "Commands:",
        "  validate                 Validate graph structure",
        "  path                     Find a shortest cross-system identity path",
    ]
    width = max(len(name) for name in COMMANDS)
    for name, (_, description) in COMMANDS.items():
        rows.append(f"  {name.ljust(width)}  {description}")
    rows += ["", "Use `data-relationship-map COMMAND --help` for command-specific arguments."]
    return "\n".join(rows)


def _invoke(main_fn: Main, program: str, args: list[str]) -> int:
    previous = sys.argv
    sys.argv = [program, *args]
    try:
        return int(main_fn())
    finally:
        sys.argv = previous


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_usage())
        return 0

    command, rest = args[0], args[1:]

    if command == "validate":
        if not rest:
            print("data-relationship-map validate: MODEL is required", file=sys.stderr)
            return 2
        return _invoke(relationship_map.main, "data-relationship-map validate", [rest[0], "validate", *rest[1:]])

    if command == "path":
        if len(rest) < 3:
            print("data-relationship-map path: MODEL FROM_ID TO_ID are required", file=sys.stderr)
            return 2
        return _invoke(relationship_map.main, "data-relationship-map path", [rest[0], "path", rest[1], rest[2], *rest[3:]])

    target = COMMANDS.get(command)
    if target is None:
        print(f"Unknown command: {command}\n", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2

    main_fn, _ = target
    return _invoke(main_fn, f"data-relationship-map {command}", rest)


if __name__ == "__main__":
    raise SystemExit(main())
