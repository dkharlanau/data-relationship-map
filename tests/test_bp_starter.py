import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bp_starter", ROOT / "scripts/rehearse_bp_starter.py")
starter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(starter)


class BpStarterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / "rehearsal"
        # Explicitly load this trusted source tree for source-suite qualification.
        # The installed runner uses a console script and has a separate check.
        bootstrap = f"import sys;sys.path.insert(0,{str(ROOT)!r});from drm_cli import main;raise SystemExit(main())"
        cls.result = starter.Starter([sys.executable, "-c", bootstrap], cls.output).run()
        cls.rows = {row["case"]: row for row in cls.result["cases"]}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_clear_crosswalk_accounting_and_time(self):
        row = self.rows["clear_crosswalk"]
        self.assertEqual((row["status"], row["source_rows"]), ("clear", 3))
        self.assertEqual(row["handoff"]["observed_at"], starter.BEFORE_TIME)

    def test_unexpected_one_to_many_is_not_a_clear_handoff(self):
        row = self.rows["unexpected_one_to_many"]
        self.assertEqual(row["summary"]["policy_finding_count"], 1)
        self.assertEqual(row["handoff"]["status"], "findings")

    def test_broken_reference_stops_before_pack(self):
        row = self.rows["broken_reference"]
        self.assertEqual(row["status"], "invalid_model")
        self.assertIsNone(row["handoff"])
        self.assertFalse((self.output / "broken_reference/handoff").exists())

    def test_orphan_is_not_silently_cleared_by_focused_pack(self):
        row = self.rows["orphan"]
        self.assertEqual(row["status"], "findings")
        self.assertEqual(row["handoff"]["status"], "clear")
        self.assertIn("outside the focused handoff", (self.output / "REVIEW.md").read_text())

    def test_conflict_keeps_node_provenance_without_a_winner(self):
        row = self.rows["metadata_conflict"]
        self.assertEqual(row["summary"]["metadata_conflict_count"], 1)
        self.assertEqual(row["handoff"]["status"], "findings")
        report = starter.read(self.output / "metadata_conflict/investigation.json")
        self.assertEqual(report["metadata_conflicts"][0]["values"],
                         ["Different supplied account label", "Sold-to legacy record"])

    def test_observation_diff_reports_the_exact_target_change(self):
        row = self.rows["changed_crosswalk"]
        self.assertEqual(row["status"], "clear")
        self.assertEqual(row["handoff"]["observed_at"], starter.AFTER_TIME)
        delta = starter.read(self.output / "snapshot-diff.json")
        self.assertEqual(delta["removed_nodes"], [starter.BP])
        self.assertEqual(delta["added_nodes"], [starter.NEXT_BP])
        self.assertEqual(delta["removed_relationships"][0]["to"], starter.BP)
        self.assertEqual(delta["added_relationships"][0]["to"], starter.NEXT_BP)

    def test_partner_link_is_not_a_selected_crosswalk(self):
        self.assertEqual(self.rows["valid_partner_assignment"]["source_rows"], 7)
        self.assertEqual(self.result["partner_connection"]["crosswalk_only"], "NO_PATH")
        self.assertIn("S4:100:0008001", self.result["partner_connection"]["unrestricted"])

    def test_abort_preserves_but_does_not_revalidate_old_graph(self):
        self.assertEqual(self.result["failed_refresh"], {
            "status": "aborted", "old_graph_unchanged": True,
            "old_graph_revalidated": False, "downstream_calls": 0})
        commands = starter.read(self.output / "commands.json")
        self.assertEqual(commands[-1]["args"][0], "import-csv")
        self.assertEqual(commands[-1]["exit"], 2)
        self.assertEqual(len(commands), 43)

    def test_existing_directory_is_never_overwritten(self):
        before = (self.output / "result.json").read_bytes()
        with self.assertRaises(FileExistsError):
            starter.Starter([sys.executable], self.output)
        self.assertEqual((self.output / "result.json").read_bytes(), before)

    def test_nonzero_tool_does_not_create_pass_result(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "failed"
            run = starter.Starter(["trusted-cli"], output)
            with patch.object(starter.subprocess, "run", return_value=subprocess.CompletedProcess([], 2, "", "failed")):
                with self.assertRaises(RuntimeError):
                    run.run()
            self.assertFalse((output / "result.json").exists())
            self.assertEqual(starter.read(output / "commands.json")[0]["exit"], 2)

    def test_source_cases_are_deterministic_and_independent_between_calls(self):
        original = starter.fixture_cases()
        changed = starter.fixture_cases()
        changed[0]["objects"].append(["not", "a", "real", "row"])
        self.assertEqual(starter.fixture_cases(), original)

    def test_sidecar_and_acceptance_limits_are_explicit(self):
        self.assertTrue(any("No PEG consumer" in x for x in self.result["limits"]))
        self.assertTrue(any("practitioner" in x for x in self.result["limits"]))
        for row in self.result["cases"]:
            if row["handoff"]:
                manifest = starter.read(self.output / row["case"] / "handoff/manifest.json")
                self.assertNotIn("import-report.json", manifest["files"])


if __name__ == "__main__":
    unittest.main()
