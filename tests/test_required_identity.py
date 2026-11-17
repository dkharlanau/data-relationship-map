"""Blank identities must not silently remove populated source rows."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import csv_adapter
import xlsx_adapter
from test_xlsx_adapter import write_minimal_xlsx

ROOT = Path(__file__).resolve().parents[1]


class RequiredIdentityTests(unittest.TestCase):
    def make_source(self, base, kind, rows):
        filename = f"source.{kind}"
        if kind == "csv":
            import csv
            with (base / filename).open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(rows)
        else:
            write_minimal_xlsx(base / filename, rows)
        return {"file": filename, **({"sheet": "Data"} if kind == "xlsx" else {})}

    def test_populated_rows_fail_for_each_empty_identity(self):
        cases = [
            ("node_sources", {"id": "{ID}"}, ["ID", "LABEL"], ["", "Missing ID"], "node id"),
            ("relationship_sources", {"from": "{FROM}", "to": "{TO}"}, ["FROM", "TO"], ["", "B"], "relationship from"),
            ("relationship_sources", {"from": "{FROM}", "to": "{TO}"}, ["FROM", "TO"], ["A", "  "], "relationship to"),
            ("relationship_sources", {"from": "{FROM}", "to": "{TO}"}, ["FROM", "TO", "NOTE"], ["", "", "Retained record"], "relationship from, to"),
        ]
        for kind, adapter in [("csv", csv_adapter), ("xlsx", xlsx_adapter)]:
            for collection, spec, header, row, field in cases:
                with self.subTest(kind=kind, field=field), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    source = self.make_source(base, kind, [header, row])
                    with self.assertRaises(ValueError) as error:
                        adapter.build_model({collection: [{**source, **spec}]}, base)
                    text = str(error.exception)
                    self.assertIn(source["file"], text)
                    self.assertIn("row 2" if kind == "xlsx" else "line 2", text)
                    self.assertIn(field + " renders empty", text)
                    if kind == "xlsx":
                        self.assertIn("sheet 'Data'", text)

    def test_padding_optional_values_and_zero_id_are_preserved(self):
        for kind, adapter in [("csv", csv_adapter), ("xlsx", xlsx_adapter)]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                source = self.make_source(base, kind, [["ID", "LABEL"], [" ", ""], ["0", ""], ["A", "Alpha"]])
                model = adapter.build_model({"node_sources": [{**source, "id": "{ID}", "label": "{LABEL}"}]}, base)
                self.assertEqual([n["id"] for n in model["nodes"]], ["0", "A"])
                self.assertEqual(model["nodes"][0]["provenance"][0]["row"], 3)

    def test_cli_rejection_preserves_existing_output_and_emits_no_partial_json(self):
        for kind in ["csv", "xlsx"]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                source = self.make_source(base, kind, [["ID", "LABEL"], ["A", "Valid"], ["", "Invalid"]])
                manifest = base / "manifest.json"
                manifest.write_text(json.dumps({"node_sources": [{**source, "id": "{ID}"}]}))
                output = base / "graph.json"
                output.write_text("existing evidence\n")
                for entry in [["drm_cli.py", f"import-{kind}"], [f"{kind}_adapter.py"]]:
                    result = subprocess.run([sys.executable, "-B", *entry, str(manifest), "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertIn("node id renders empty", result.stderr)
                    self.assertEqual(output.read_text(), "existing evidence\n")
                output.unlink()
                result = subprocess.run([sys.executable, "-B", "drm_cli.py", f"import-{kind}", str(manifest), "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
