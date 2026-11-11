"""Explicit identity components are a source contract, not a guessed SAP key."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import csv_adapter
import xlsx_adapter
from test_xlsx_adapter import write_minimal_xlsx

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = {"csv": csv_adapter, "xlsx": xlsx_adapter}


class IdentityColumnsTests(unittest.TestCase):
    def source(self, base, kind, rows):
        name = "crosswalk." + kind
        if kind == "csv":
            with (base / name).open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerows(rows)
        else:
            write_minimal_xlsx(base / name, rows, sheet_name="Crosswalk")
        return {"file": name, **({"sheet": "Crosswalk"} if kind == "xlsx" else {})}

    def test_partial_composite_identity_is_rejected_when_declared(self):
        for kind, adapter in ADAPTERS.items():
            for field in ("CLIENT", "ID"):
                with self.subTest(kind=kind, field=field), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    values = {"CLIENT": "100", "ID": "0004711", "LABEL": "private-value-never-echo"}
                    values[field] = " \t "
                    source = self.source(base, kind, [list(values), list(values.values())])
                    source.update(id="S4:{CLIENT}:{ID}", required_identity_columns=["CLIENT", "ID"])
                    with self.assertRaises(ValueError) as caught:
                        adapter.build_model({"node_sources": [source]}, base)
                    error = str(caught.exception)
                    self.assertIn("required identity columns are blank", error)
                    self.assertIn(field, error)
                    self.assertIn(source["file"], error)
                    self.assertIn("row 2" if kind == "xlsx" else "line 2", error)
                    self.assertNotIn("private-value-never-echo", error)
                    if kind == "xlsx": self.assertIn("sheet 'Crosswalk'", error)

    def test_relationship_components_are_checked_for_both_endpoints(self):
        for kind, adapter in ADAPTERS.items():
            for field in ("FROM", "TO"):
                with self.subTest(kind=kind, field=field), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    values = {"FROM": "A", "TO": "B"}; values[field] = ""
                    source = self.source(base, kind, [list(values), list(values.values())])
                    source.update({"from": "ERP:{FROM}", "to": "S4:{TO}", "required_identity_columns": ["FROM", "TO"]})
                    with self.assertRaisesRegex(ValueError, "required identity columns are blank"):
                        adapter.build_model({"relationship_sources": [source]}, base)

    def test_valid_output_identical_and_ids_remain_text(self):
        for kind, adapter in ADAPTERS.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                source = self.source(base, kind, [["CLIENT", "ID", "LABEL"], ["100", "0004711", ""], ["200", "0004711", ""], ["100", "0", ""]])
                source.update(id="S4:{CLIENT}:{ID}", label="{LABEL}")
                before = adapter.build_model({"node_sources": [source]}, base)
                source["required_identity_columns"] = ["CLIENT", "ID"]
                after = adapter.build_model({"node_sources": [source]}, base)
                self.assertEqual(before, after)
                self.assertEqual([n["id"] for n in after["nodes"]], ["S4:100:0004711", "S4:200:0004711", "S4:100:0"])

    def test_no_policy_is_inferred_when_declaration_absent_or_empty(self):
        for kind, adapter in ADAPTERS.items():
            for declaration in (None, []):
                with self.subTest(kind=kind, declaration=declaration), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    source = self.source(base, kind, [["ID", "LABEL"], ["", "Populated"]])
                    source["id"] = "X:{ID}"
                    if declaration is not None: source["required_identity_columns"] = declaration
                    self.assertEqual(adapter.build_model({"node_sources": [source]}, base)["nodes"][0]["id"], "X:")

    def test_missing_declared_header_rejected_even_without_data_rows(self):
        for kind, adapter in ADAPTERS.items():
            for rows in ([["OTHER"]], [["OTHER"], ["a"]], [["OTHER"], [""]]):
                with self.subTest(kind=kind, rows=rows), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    source = self.source(base, kind, rows)
                    source.update(id="CONSTANT", required_identity_columns=["ID"])
                    with self.assertRaisesRegex(ValueError, "required identity columns missing from header"):
                        adapter.build_model({"node_sources": [source]}, base)

    def test_invalid_declarations_rejected_on_empty_sources(self):
        for kind, adapter in ADAPTERS.items():
            for value in (None, "ID", True, {}, [1], [""], ["  "], ["ID", "ID"]):
                with self.subTest(kind=kind, value=value), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    source = self.source(base, kind, [["ID"]])
                    source.update(id="X:{ID}", required_identity_columns=value)
                    with self.assertRaisesRegex(ValueError, "required_identity_columns") as caught:
                        adapter.build_model({"node_sources": [source]}, base)
                    self.assertIn(source["file"], str(caught.exception))
                    if kind == "xlsx": self.assertIn("sheet 'Crosswalk'", str(caught.exception))

    def test_completely_empty_worksheet_cannot_satisfy_declared_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = self.source(base, "xlsx", [])
            source.update(id="X:{ID}", required_identity_columns=["ID"])
            with self.assertRaisesRegex(ValueError, "cannot be checked without a header"):
                xlsx_adapter.build_model({"node_sources": [source]}, base)

    def test_blank_padding_keeps_physical_row_and_multiline_provenance(self):
        for kind, adapter in ADAPTERS.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                source = self.source(base, kind, [["ID", "LABEL"], [" ", ""], ["001", "line1\nline2"], ["", "Invalid"]])
                source.update(id="X:{ID}", required_identity_columns=["ID"])
                with self.assertRaises(ValueError) as caught:
                    adapter.build_model({"node_sources": [source]}, base)
                self.assertIn("row 4" if kind == "xlsx" else "line 5", str(caught.exception))

    def test_contract_applies_after_existing_xlsx_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = self.source(base, "xlsx", [["ID", "CLIENT"], [" 0001 ", "100"]])
            source.update(id="S4:{CLIENT}:{ID}", required_identity_columns=["ID", "CLIENT"], normalizers={"ID": "strip"})
            model = xlsx_adapter.build_model({"node_sources": [source]}, base)
            self.assertEqual(model["nodes"][0]["id"], "S4:100:0001")
            self.assertEqual(model["nodes"][0]["provenance"][0]["raw_identity"], "S4:100: 0001")

    def test_empty_boolean_cells_are_not_synthesized_as_false_identities(self):
        for value, expected in ((None, ""), ("", ""), ("  \t ", ""), ("0", "FALSE"), ("1", "TRUE")):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                source = self.source(base, "xlsx", [["ID", "NOTE"], ["placeholder", "Populated row"]])
                path = base / source["file"]
                with zipfile.ZipFile(path) as archive:
                    parts = {name: archive.read(name) for name in archive.namelist()}
                ns = "{" + xlsx_adapter.MAIN_NS + "}"
                tree = ET.fromstring(parts["xl/worksheets/sheet1.xml"])
                cell = tree.find(f".//{ns}c[@r='A2']")
                cell.clear(); cell.attrib.update(r="A2", t="b")
                if value is not None: ET.SubElement(cell, ns + "v").text = value
                parts["xl/worksheets/sheet1.xml"] = ET.tostring(tree)
                with zipfile.ZipFile(path, "w") as archive:
                    for name, data in parts.items(): archive.writestr(name, data)
                self.assertEqual(list(xlsx_adapter.read_sheet(path, "Crosswalk"))[0][1]["ID"], expected)
                source.update(id="X:{ID}", required_identity_columns=["ID"])
                if expected:
                    self.assertEqual(xlsx_adapter.build_model({"node_sources": [source]}, base)["nodes"][0]["id"], "X:" + expected)
                else:
                    with self.assertRaisesRegex(ValueError, "required identity columns are blank"):
                        xlsx_adapter.build_model({"node_sources": [source]}, base)
                    source.update(id="FIXED", label="{ID}", required_identity_columns=[])
                    self.assertEqual(xlsx_adapter.build_model({"node_sources": [source]}, base)["nodes"][0]["label"], "")

    def test_cli_rejection_preserves_output_and_has_no_partial_graph(self):
        for kind in ADAPTERS:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                source = self.source(base, kind, [["CLIENT", "ID"], ["100", "001"], ["100", ""]])
                source.update(id="S4:{CLIENT}:{ID}", required_identity_columns=["CLIENT", "ID"])
                manifest = base / "manifest.json"
                manifest.write_text(json.dumps({"node_sources": [source]}))
                for entry in ([f"{kind}_adapter.py"], ["drm_cli.py", "import-" + kind]):
                    for exists in (False, True):
                        output = base / ("existing.json" if exists else "absent.json")
                        if exists: output.write_bytes(b"retained previous evidence\n")
                        result = subprocess.run([sys.executable, "-B", *entry, str(manifest), "-o", str(output)], cwd=ROOT, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 2, result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertNotIn("Traceback", result.stderr)
                        self.assertIn("required identity columns are blank", result.stderr)
                        if exists: self.assertEqual(output.read_bytes(), b"retained previous evidence\n")
                        else: self.assertFalse(output.exists())


if __name__ == "__main__": unittest.main()
