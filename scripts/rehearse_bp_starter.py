#!/usr/bin/env python3
"""Run the repository's synthetic BP investigation cases through the DRM CLI."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

FOCUS = "LEGACY:100:0004711"
BP = "MDG:100:0009001"
NEXT_BP = "MDG:100:0009002"
BEFORE_TIME = "2026-08-25T10:00:00Z"
AFTER_TIME = "2026-08-26T10:00:00Z"
SOURCE = Path(__file__).resolve().parents[1] / "examples/bp-connection-paths"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_cases():
    """Derive named scenarios from the existing, inspectable CSV starter."""
    with (SOURCE / "objects.csv").open(newline="", encoding="utf-8") as handle:
        objects = list(csv.reader(handle))
    with (SOURCE / "crosswalk.csv").open(newline="", encoding="utf-8") as handle:
        crosswalk = list(csv.reader(handle))
    with (SOURCE / "partners.csv").open(newline="", encoding="utf-8") as handle:
        partners = list(csv.reader(handle))
    common = dict(objects=objects[:3], crosswalk=crosswalk, partners=partners[:1])
    extra_bp = ["MDG", "100", "0009002", "Second supplied partner"]
    second_link = ["LEGACY", "100", "0004711", "MDG", "100", "0009002"]
    return [
        dict(name="clear_crosswalk", **common, status="clear", observed=BEFORE_TIME,
             action="Confirm that the supplied crosswalk is appropriate for the comparison key."),
        dict(name="unexpected_one_to_many", objects=objects[:3] + [extra_bp],
             crosswalk=crosswalk + [second_link], partners=partners[:1],
             status="findings", observed=BEFORE_TIME,
             action="Ask which target mapping is intended; do not choose a candidate automatically."),
        dict(name="broken_reference", objects=objects[:2], crosswalk=crosswalk,
             partners=partners[:1], status="invalid_model", observed=BEFORE_TIME,
             action="Supply or correct the absent target object before making a handoff."),
        dict(name="orphan", objects=objects[:3] + [extra_bp], crosswalk=crosswalk,
             partners=partners[:1], status="findings", observed=BEFORE_TIME,
             action="Review the unlinked object separately; the focused handoff excludes it."),
        dict(name="metadata_conflict", objects=objects[:3] + [
             ["LEGACY", "100", "0004711", "Different supplied account label"]],
             crosswalk=crosswalk, partners=partners[:1], status="findings",
             observed=BEFORE_TIME,
             action="Inspect both descriptions and contributing node rows; no winner is endorsed."),
        dict(name="changed_crosswalk", objects=objects[:2] + [extra_bp],
             crosswalk=crosswalk[:1] + [second_link], partners=partners[:1],
             status="clear", observed=AFTER_TIME,
             action="A locally clear snapshot still changed its target; decide whether the change was intended."),
        dict(name="separate_client_namespaces",
             objects=objects[:3] + [["LEGACY", "200", "0004711", "Other client account"],
                                   ["MDG", "200", "0009001", "Other client partner"]],
             crosswalk=crosswalk + [["LEGACY", "200", "0004711", "MDG", "200", "0009001"]],
             partners=partners[:1], status="clear", observed=BEFORE_TIME,
             action="Keep identical display IDs in different supplied client namespaces separate."),
        dict(name="valid_partner_assignment", objects=objects, crosswalk=crosswalk,
             partners=partners, status="clear", observed=BEFORE_TIME,
             action="Keep partner assignments separate from identity claims, even when a connection exists."),
    ]


class Starter:
    def __init__(self, command, output, *, source_format="csv"):
        require(source_format in ("csv", "xlsx"), "Unsupported source format.")
        require(bool(command), "A trusted DRM command is required.")
        self.source_format = source_format
        self.command = list(map(str, command))
        # Never reuse or clear an existing directory, including a symlink.
        self.output = Path(output).absolute()
        self.output.mkdir(parents=True, exist_ok=False)
        self.commands = []

    def source_ref(self, name, row):
        ref = {"file": f"{name}.{self.source_format}", "row": row}
        if self.source_format == "xlsx":
            ref["sheet"] = name
        return ref

    def write_source(self, directory, name, rows):
        destination = directory / f"{name}.{self.source_format}"
        if self.source_format == "csv":
            with destination.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle, lineterminator="\n").writerows(rows)
        else:
            # Reuse the repository's existing dependency-free synthetic writer.
            source = SOURCE.parents[1] / "examples/xlsx/make_sample.py"
            spec = importlib.util.spec_from_file_location("bp_synthetic_xlsx", source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.build(destination, rows=rows, sheet_name=name)

    def manifest(self):
        manifest = read(SOURCE / "manifest.json")
        if self.source_format == "xlsx":
            for group in ("node_sources", "relationship_sources"):
                for entry in manifest[group]:
                    stem = Path(entry["file"]).stem
                    entry.update(file=stem + ".xlsx", sheet=stem)
        return manifest

    def call(self, args, expected=0):
        env = dict(os.environ)
        for key in ("PYTHONPATH", "PYTHONHOME"):
            env.pop(key, None)
        env["PYTHONSAFEPATH"] = "1"
        result = subprocess.run(self.command + list(map(str, args)),
                                cwd=self.output, env=env, capture_output=True,
                                text=True, timeout=60, check=False)
        self.commands.append(dict(args=list(map(str, args)), exit=result.returncode,
                                  stdout=result.stdout, stderr=result.stderr))
        write(self.output / "commands.json", self.commands)
        require(result.returncode == expected, "Unexpected CLI result; inspect commands.json.")
        return result

    def run(self):
        rows = []
        for case in fixture_cases():
            d = self.output / case["name"]
            d.mkdir()
            for name in ("objects", "crosswalk", "partners"):
                self.write_source(d, name, case[name])
            write(d / "manifest.json", self.manifest())
            write(d / "policy.json", read(SOURCE / "policy.json"))
            graph, accounting = d / "graph.json", d / "import-report.json"
            self.call(["import-" + self.source_format, d / "manifest.json", "--output", graph,
                       "--import-report", accounting])
            imported = read(accounting)
            count = sum(len(case[name]) - 1 for name in ("objects", "crosswalk", "partners"))
            require(imported["complete"] is True and imported["model_returned"] is True,
                    "Incomplete producer must not reach analysis.")
            require(imported["counts"] == dict(encountered=count, accepted=count, skipped=0, rejected=0),
                    "Unexpected source-declaration accounting.")
            valid = json.loads(self.call(["validate", graph],
                               1 if case["status"] == "invalid_model" else 0).stdout)
            self.call(["investigate", graph, "--policy", d / "policy.json", "--focus", FOCUS,
                       "--json-output", d / "investigation.json", "--markdown", d / "investigation.md",
                       "--html", d / "investigation.html"], 0 if case["status"] == "clear" else 1)
            report = read(d / "investigation.json")
            require(report["status"] == case["status"], "Unexpected investigation status.")
            summary = report["summary"]
            if case["name"] == "unexpected_one_to_many":
                require(summary["policy_finding_count"] == 1, "Expected exactly one cardinality finding.")
            if case["name"] == "metadata_conflict":
                require(summary.get("metadata_conflict_count") == 1, "Expected one recorded label conflict.")
                require(report["metadata_conflicts"][0]["contributing_node_provenance"] ==
                        [self.source_ref("objects", 2), self.source_ref("objects", 4)],
                        "Contributing node provenance changed.")
            if case["name"] == "orphan":
                require(report["structural"]["orphans"] == [NEXT_BP], "Expected unlinked target object.")
            model = read(graph)
            require(model["relationships"][0]["provenance"] == self.source_ref("crosswalk", 2),
                    "Source crosswalk row not retained.")
            if case["name"] == "separate_client_namespaces":
                require({n["id"] for n in model["nodes"]} ==
                        {FOCUS, BP, "LEGACY:200:0004711", "MDG:200:0009001"},
                        "Supplied client namespaces or leading zeros were lost.")
            pack = d / "handoff"
            self.call(["handoff", "build", graph, pack, "--focus", FOCUS, "--max-depth", "2",
                       "--policy", d / "policy.json", "--observed-at", case["observed"]],
                      2 if case["status"] == "invalid_model" else 0)
            bounded = None
            if not valid["valid"]:
                require(not pack.exists(), "Broken graph unexpectedly produced a handoff.")
            else:
                verified = json.loads(self.call(["handoff", "verify", pack]).stdout)
                require(verified["valid"] is True, "Retained integrity failed.")
                index, retained = read(pack / "artifact-index.json"), read(pack / "manifest.json")
                require(index["observed_at"] == case["observed"], "Authored fixture time was not retained.")
                require("import-report.json" not in retained["files"], "Unexpected sidecar scope.")
                if case["name"] == "orphan":
                    require(retained["status"] == "clear" and
                            NEXT_BP not in {n["id"] for n in read(pack / "graph.json")["nodes"]},
                            "Expected orphan outside focused handoff.")
                if case["name"] == "separate_client_namespaces":
                    require({n["id"] for n in read(pack / "graph.json")["nodes"]} == {FOCUS, BP},
                            "Another client entered the focused handoff.")
                bounded = dict(status=retained["status"], pack_id=retained["pack_id"],
                               observed_at=index["observed_at"], integrity=True)
            rows.append(dict(case=case["name"], source_rows=count, import_complete=True,
                             status=report["status"], summary=report["summary"], handoff=bounded,
                             next_action=case["action"]))
        before = self.output / "clear_crosswalk"
        after = self.output / "changed_crosswalk"
        delta = json.loads(self.call(["diff", before / "graph.json", after / "graph.json"]).stdout)
        require(delta["removed_relationships"] == [dict(**{"from": FOCUS, "type": "explicit_crosswalk", "to": BP})]
                and delta["added_relationships"] == [dict(**{"from": FOCUS, "type": "explicit_crosswalk", "to": NEXT_BP})],
                "Expected target change was not reported.")
        write(self.output / "snapshot-diff.json", delta)
        pgraph = self.output / "valid_partner_assignment/graph.json"
        unrestricted = self.call(["path", pgraph, FOCUS, "S4:100:0008001"]).stdout.strip()
        selected = self.call(["path", pgraph, FOCUS, "S4:100:0008001",
                              "--relation", "explicit_crosswalk"], 2).stdout.strip()
        require(selected == "NO_PATH", "Partner connection was treated as a selected crosswalk.")
        # Deliberately abort a refresh of a copy, then do no downstream work on it.
        failed = self.output / "failed_refresh"
        failed.mkdir()
        (failed / "graph.json").write_bytes((before / "graph.json").read_bytes())
        for name in ("manifest.json", *[f"{name}.{self.source_format}" for name in ("objects", "crosswalk", "partners")]):
            (failed / name).write_bytes((before / name).read_bytes())
        self.write_source(failed, "objects", [["SYSTEM", "CLIENT", "ID", "LABEL"],
                                             ["LEGACY", "100", "", "Missing source ID"]])
        old_hash = digest(failed / "graph.json")
        self.call(["import-" + self.source_format, failed / "manifest.json", "--output", failed / "graph.json",
                   "--import-report", failed / "import-report.json"], 2)
        aborted = read(failed / "import-report.json")
        require(aborted["complete"] is False and aborted["model_returned"] is False,
                "Expected incomplete import.")
        require(old_hash == digest(failed / "graph.json"), "Failed refresh overwrote the old graph.")
        require(not (failed / "handoff").exists(), "Aborted import reached downstream work.")
        result = dict(status="passed", source_format=self.source_format, cases=rows, cli_invocations=len(self.commands),
                      snapshot_comparison=dict(before="clear_crosswalk", after="changed_crosswalk",
                                               authored_before=BEFORE_TIME, authored_after=AFTER_TIME,
                                               artifact="snapshot-diff.json"),
                      partner_connection=dict(unrestricted=unrestricted, crosswalk_only=selected),
                      failed_refresh=dict(status=aborted["status"], old_graph_unchanged=True,
                                          old_graph_revalidated=False, downstream_calls=0),
                      limits=["Synthetic export cases and authored observation times, not live SAP.",
                              "Found connection, policy result and byte integrity are not business approval.",
                              "Import report is separate from the verified handoff.",
                              "No PEG consumer invoked; retained handoff is the boundary.",
                              "Three SAP/data practitioner reviews remain outstanding."])
        lines = ["# Synthetic BP starter review", "", "Automated expectations passed; business acceptance is not established.", "",
                 "| Case | Full investigation | Focused handoff | Next human decision |",
                 "| --- | --- | --- | --- |"]
        for row in rows:
            state = row["handoff"]["status"] if row["handoff"] else "stopped"
            lines.append(f'| {row["case"]} | {row["status"]} | {state} | {row["next_action"]} |')
        lines += ["", "The orphan is outside the focused handoff. A clear subset does not clear the full source.",
                  "Before/after times are authored fixture labels, not detected change time or causation.",
                  "Failed refresh: old graph preserved but NOT revalidated; no handoff made.",
                  "Partner-only connection is not accepted as crosswalk-only identity evidence.",
                  "Import sidecars remain outside pack integrity. No PEG run or practitioner acceptance.", ""]
        (self.output / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
        write(self.output / "result.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drm-cli", type=Path, required=True, help="Trusted installed data-relationship-map executable")
    parser.add_argument("--format", choices=("csv", "xlsx"), default="csv",
                        help="Generate CSV or inline-string XLSX exports from the same synthetic cells")
    parser.add_argument("--output", type=Path, required=True, help="New output directory, never overwritten")
    args = parser.parse_args()
    try:
        executable = args.drm_cli.resolve(strict=True)
        result = Starter([executable], args.output, source_format=args.format).run()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print("BP starter did not complete; inspect retained outputs. No existing directory is cleared.", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
