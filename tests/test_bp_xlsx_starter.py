import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bp_xlsx_starter", ROOT / "scripts/rehearse_bp_starter.py")
starter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(starter)
writer_spec = importlib.util.spec_from_file_location("bp_writer", ROOT / "examples/xlsx/make_sample.py")
writer = importlib.util.module_from_spec(writer_spec)
writer_spec.loader.exec_module(writer)


def semantics(model):
    return {kind: [{k: v for k, v in item.items() if k != "provenance"} for item in model[kind]]
            for kind in ("nodes", "relationships")}


class BpXlsxStarterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.results = {}
        bootstrap = f"import sys;sys.path.insert(0,{str(ROOT)!r});from drm_cli import main;raise SystemExit(main())"
        for fmt in ("csv", "xlsx"):
            cls.results[fmt] = starter.Starter([sys.executable, "-c", bootstrap],
                                              cls.root / fmt, source_format=fmt).run()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_eight_case_semantics_match_without_erasing_source_provenance(self):
        self.assertEqual(len(self.results["xlsx"]["cases"]), 8)
        for case in self.results["csv"]["cases"]:
            name = case["case"]
            before = starter.read(self.root / "csv" / name / "graph.json")
            after = starter.read(self.root / "xlsx" / name / "graph.json")
            self.assertEqual(semantics(before), semantics(after), name)
            self.assertNotEqual(before["nodes"][0]["provenance"], after["nodes"][0]["provenance"])

    def test_same_display_id_different_clients_stays_separate(self):
        for fmt in ("csv", "xlsx"):
            case = self.root / fmt / "separate_client_namespaces"
            graph = starter.read(case / "graph.json")
            self.assertEqual({n["id"] for n in graph["nodes"]},
                             {starter.FOCUS, starter.BP, "LEGACY:200:0004711", "MDG:200:0009001"})
            self.assertEqual(len(graph["relationships"]), 2)
            self.assertEqual({n["id"] for n in starter.read(case / "handoff/graph.json")["nodes"]},
                             {starter.FOCUS, starter.BP})

    def test_xlsx_preserves_leading_zeros_and_explicit_sheet_row(self):
        graph = starter.read(self.root / "xlsx/clear_crosswalk/graph.json")
        self.assertEqual(graph["nodes"][0]["id"], "LEGACY:100:0004711")
        self.assertEqual(graph["nodes"][0]["provenance"],
                         [{"file": "objects.xlsx", "row": 2, "sheet": "objects"}])
        self.assertEqual(graph["relationships"][0]["provenance"],
                         {"file": "crosswalk.xlsx", "row": 2, "sheet": "crosswalk"})

    def test_header_only_partner_sheet_has_zero_records_not_a_failure(self):
        report = starter.read(self.root / "xlsx/clear_crosswalk/import-report.json")
        source = next(s for s in report["sources"] if s["file"] == "partners.xlsx")
        self.assertEqual(source["records"], [])
        self.assertEqual(source["status"], "complete")
        self.assertEqual(source["sheet"], "partners")

    def test_status_summary_and_accounting_match_between_adapters(self):
        for left, right in zip(self.results["csv"]["cases"], self.results["xlsx"]["cases"]):
            for key in ("case", "source_rows", "status", "summary", "import_complete"):
                self.assertEqual(left[key], right[key])
            for fmt in ("csv", "xlsx"):
                report = starter.read(self.root / fmt / left["case"] / "import-report.json")
                self.assertEqual(report["counts"]["accepted"], left["source_rows"])

    def test_pack_identity_is_not_transferred_between_file_formats(self):
        for left, right in zip(self.results["csv"]["cases"], self.results["xlsx"]["cases"]):
            if left["handoff"]:
                self.assertEqual(left["handoff"]["status"], right["handoff"]["status"])
                self.assertNotEqual(left["handoff"]["pack_id"], right["handoff"]["pack_id"])

    def test_changed_relationship_and_partner_refusal_match(self):
        self.assertEqual(starter.read(self.root / "csv/snapshot-diff.json"),
                         starter.read(self.root / "xlsx/snapshot-diff.json"))
        self.assertEqual(self.results["csv"]["partner_connection"],
                         self.results["xlsx"]["partner_connection"])

    def test_xlsx_abort_does_not_run_downstream_or_change_prior_graph(self):
        result = self.results["xlsx"]
        self.assertEqual(result["cli_invocations"], 43)
        self.assertEqual(result["failed_refresh"], self.results["csv"]["failed_refresh"])
        commands = starter.read(self.root / "xlsx/commands.json")
        self.assertEqual(commands[-1]["args"][0], "import-xlsx")
        self.assertEqual(commands[-1]["exit"], 2)
        report = starter.read(self.root / "xlsx/failed_refresh/import-report.json")
        self.assertFalse(report["complete"])
        self.assertEqual(report["sources"][0]["records"][0]["reason"], "blank_identity_component")

    def test_no_implicit_normalizer_added_to_manifest(self):
        for fmt in ("csv", "xlsx"):
            manifest = starter.read(self.root / fmt / "separate_client_namespaces/manifest.json")
            self.assertNotIn("normalizers", manifest)
            self.assertTrue(all("normalizers" not in s for group in ("node_sources", "relationship_sources")
                                for s in manifest[group]))

    def test_unsupported_format_refuses_before_output_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "refused"
            with self.assertRaises(RuntimeError):
                starter.Starter(["trusted"], output, source_format="xls")
            self.assertFalse(output.exists())

    def test_reused_generator_writes_inert_strings_and_escaped_sheet_name(self):
        from xlsx_adapter import read_sheet
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "strings.xlsx"
            writer.build(output, rows=[["ID", "LABEL"], ["0004711", "A<&>"], ["0", "=SUM(A1:A2)"]],
                         sheet_name='A & "B"')
            rows = list(read_sheet(output, 'A & "B"'))
            self.assertEqual(rows, [(2, {"ID": "0004711", "LABEL": "A<&>"}),
                                    (3, {"ID": "0", "LABEL": "=SUM(A1:A2)"})])
            with zipfile.ZipFile(output) as book:
                self.assertIsNone(book.testzip())
                self.assertNotIn(b"<f>", book.read("xl/worksheets/sheet1.xml"))

    def test_default_generator_still_imports_original_crosswalk(self):
        from xlsx_adapter import read_sheet
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "original.xlsx"
            writer.build(output)
            rows = list(read_sheet(output, "Crosswalk"))
            self.assertEqual([r[1]["AFS_KUNNR"] for r in rows], ["0004711", "0004712"])


if __name__ == "__main__":
    unittest.main()
