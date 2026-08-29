import unittest

from relationship_investigation import build_investigation, render_markdown


class InvestigationReportTests(unittest.TestCase):
    def setUp(self):
        self.clean_model = {
            "nodes": [
                {
                    "id": "AFS:4711",
                    "system": "AFS",
                    "object": "customer",
                    "provenance": [{"file": "crosswalk.csv", "row": 2}],
                },
                {
                    "id": "MDG:7200311",
                    "system": "MDG",
                    "object": "business-partner",
                },
            ],
            "relationships": [
                {
                    "from": "AFS:4711",
                    "to": "MDG:7200311",
                    "type": "mapped_to",
                    "provenance": {"file": "crosswalk.csv", "row": 2},
                }
            ],
        }
        self.policy = {
            "relationship_rules": {
                "mapped_to": {"max_outgoing": 1, "max_incoming": 1}
            },
            "report_identity_collisions": True,
            "fail_on_identity_collisions": True,
        }

    def test_clear_report_combines_policy_lineage_and_provenance(self):
        report = build_investigation(
            self.clean_model,
            policy=self.policy,
            focus="AFS:4711",
            max_depth=2,
        )
        self.assertEqual(report["status"], "clear")
        self.assertEqual(report["summary"]["structural_finding_count"], 0)
        self.assertEqual(report["summary"]["policy_finding_count"], 0)
        self.assertEqual(report["focus"]["downstream"]["paths"]["MDG:7200311"], ["AFS:4711", "MDG:7200311"])
        self.assertEqual(len(report["focus"]["source_references"]), 2)

        markdown = render_markdown(report)
        self.assertIn("**Status:** `clear`", markdown)
        self.assertIn("crosswalk.csv", markdown)
        self.assertIn("Downstream context", markdown)

    def test_policy_ambiguity_becomes_findings(self):
        ambiguous = {
            "nodes": [
                {"id": "A", "system": "LEGACY", "object": "customer"},
                {"id": "B", "system": "MDG", "object": "business-partner"},
                {"id": "C", "system": "MDG", "object": "business-partner"},
            ],
            "relationships": [
                {"from": "A", "to": "B", "type": "mapped_to"},
                {"from": "A", "to": "C", "type": "mapped_to"},
            ],
        }
        report = build_investigation(ambiguous, policy=self.policy, focus="A")
        self.assertEqual(report["status"], "findings")
        self.assertEqual(report["summary"]["policy_finding_count"], 1)
        self.assertEqual(report["policy"]["cardinality_violations"][0]["related_ids"], ["B", "C"])
        self.assertIn("Cardinality violation", render_markdown(report))

    def test_broken_graph_is_invalid_model(self):
        broken = {
            "nodes": [{"id": "A", "system": "LEGACY", "object": "customer"}],
            "relationships": [{"from": "A", "to": "MISSING", "type": "mapped_to"}],
        }
        report = build_investigation(broken, policy=self.policy)
        self.assertEqual(report["status"], "invalid_model")
        self.assertEqual(report["summary"]["structural_finding_count"], 2)

    def test_missing_focus_fails_loudly(self):
        report = build_investigation(self.clean_model, policy=self.policy, focus="NOT-THERE")
        self.assertEqual(report["status"], "invalid_focus")
        self.assertFalse(report["focus"]["valid"])


if __name__ == "__main__":
    unittest.main()
