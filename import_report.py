"""Optional, bounded import accounting. This sidecar is not a graph approval."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import zipfile
from xml.etree import ElementTree as ET
from typing import Any


IMPORT_ERRORS = (ValueError, OSError, KeyError, IndexError, AttributeError, TypeError, zipfile.BadZipFile, ET.ParseError)


class ImportRecordError(ValueError):
    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


class ImportReport:
    """Count source-declaration/record pairs, not distinct physical input rows.

    An abort reports only observations up to the first error. No claim is made
    about unvisited rows, and accepted outputs on an aborted import are provisional.
    """

    def __init__(self, target: dict[str, Any] | None, adapter: str, manifest: dict[str, Any]):
        self.target = target
        self.current = None
        self.pending = None
        if target is not None:
            target.clear()
            target.update(format="data-relationship-map-import-report/1.0", adapter=adapter,
                          status="in_progress", complete=False, model_returned=False,
                          counting_unit="source_declaration_record", sources=[])
            try:
                for kind in ("node_sources", "relationship_sources"):
                    for index, spec in enumerate(manifest.get(kind, [])):
                        source = dict(source_id=f"{kind}/{index}", file=spec["file"],
                                      status="not_started", records=[])
                        if adapter == "xlsx":
                            source["sheet"] = str(spec.get("sheet", "Sheet1"))
                        target["sources"].append(source)
            except IMPORT_ERRORS as exc:
                target["error"] = "manifest_contract_error"
                self.abort(exc)
                raise

    def source(self, kind: str, index: int) -> None:
        if self.target is None:
            return
        if self.current is not None:
            self.current["status"] = "complete"
        self.current = next(s for s in self.target["sources"] if s["source_id"] == f"{kind}/{index}")
        self.current["status"] = "in_progress"
        self.pending = None

    def row(self, number: int, end: int | None = None) -> None:
        if self.target is not None:
            self.pending = {"row": number, "row_end": end if end is not None else number}

    def end_row(self, end: int) -> None:
        if self.pending is not None:
            self.pending["row_end"] = end

    def record(self, disposition: str, reason: str, output: dict[str, Any] | None = None) -> None:
        if self.target is None:
            return
        if self.pending is None or self.current is None:
            raise RuntimeError("Import accounting requires a pending source row")
        self.pending.update(disposition=disposition, reason=reason, outputs=[] if output is None else [output])
        self.current["records"].append(self.pending)
        self.pending = None

    def finish(self) -> None:
        if self.target is not None:
            if self.current is not None:
                self.current["status"] = "complete"
            self.target.update(status="complete", complete=True, model_returned=True)
            self._counts()

    def abort(self, error: Exception) -> None:
        if self.target is not None:
            if self.current is not None:
                self.current["status"] = "aborted"
                if self.pending is not None:
                    self.record("rejected", getattr(error, "reason", "invalid_record"))
                else:
                    self.current["error"] = "source_or_contract_error"
            self.target.update(status="aborted", complete=False, model_returned=False)
            self._counts()

    def _counts(self) -> None:
        totals = dict(encountered=0, accepted=0, skipped=0, rejected=0)
        for source in self.target["sources"]:
            counts = dict(encountered=len(source["records"]), accepted=0, skipped=0, rejected=0)
            for record in source["records"]:
                counts[record["disposition"]] += 1
            source["counts"] = counts
            for key in totals:
                totals[key] += counts[key]
        self.target["counts"] = totals


def validate_output_paths(manifest_path: Path, manifest: dict[str, Any], base_dir: Path,
                          output_path: str | None, report_path: str) -> None:
    """Reject existing aliases, including hardlinks, before writing either output.

    This is an ordinary local-file guard, not a guarantee against concurrent
    path replacement by another process.
    """
    inputs = [manifest_path] + [base_dir / spec["file"]
                                for kind in ("node_sources", "relationship_sources")
                                for spec in manifest.get(kind, [])]
    outputs = [Path(report_path)] + ([Path(output_path)] if output_path else [])
    def aliases(a: Path, b: Path) -> bool:
        return a.resolve() == b.resolve() or (a.exists() and b.exists() and a.samefile(b))
    if len(outputs) == 2 and aliases(*outputs):
        raise ValueError("graph and import report must use distinct output paths")
    if any(aliases(out, inp) for out in outputs for inp in inputs):
        raise ValueError("import outputs must not overwrite the manifest or a source file")


def write_report(path: str, report: dict[str, Any]) -> None:
    """Replace one sidecar atomically; graph+report are not a transactional pair."""
    write_text_atomic(path, json.dumps(report, indent=2, ensure_ascii=False) + "\n")


def write_text_atomic(path: str, payload: str) -> None:
    destination = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".drm-report-", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
