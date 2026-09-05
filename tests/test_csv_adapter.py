import tempfile
import unittest
from pathlib import Path

from csv_adapter import build_model, read_rows
from relationship_map import analyze, shortest_path


class CsvAdapterTests(unittest.TestCase):
    def test_malformed_exports_cannot_silently_change_identity(self):
        cases = [
            ("ID,ID\noriginal,overwritten\n", "duplicate"),
            ("ID,\n1,unlabelled\n", "empty column"),
            ("ID,NAME\n1\n", "line 2"),
            ("ID,NAME\n1,A,extra\n", "line 2"),
            ('ID,NAME\n1,"unclosed\n', "Invalid CSV"),
            ("", "no header"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.csv"
            for content, message in cases:
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        list(read_rows(path))

    def test_multiline_values_keep_the_physical_source_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.csv"
            path.write_text('\ufeffID,NAME\n1,"First\nsecond"\n\n2,\n', encoding="utf-8")
            self.assertEqual(list(read_rows(path)), [
                (2, {"ID": "1", "NAME": "First\nsecond"}),
                (5, {"ID": "2", "NAME": ""}),
            ])

    def test_build_model_from_crosswalk(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "crosswalk.csv").write_text(
                "AFS,MDG,S4\n4711,7200311,10000345\n", encoding="utf-8"
            )
            manifest = {
                "node_sources": [
                    {"file": "crosswalk.csv", "id": "AFS:{AFS}", "system": "AFS", "object": "customer"},
                    {"file": "crosswalk.csv", "id": "MDG:{MDG}", "system": "MDG", "object": "business-partner"},
                    {"file": "crosswalk.csv", "id": "S4:{S4}", "system": "S4", "object": "business-partner"},
                ],
                "relationship_sources": [
                    {"file": "crosswalk.csv", "from": "AFS:{AFS}", "to": "MDG:{MDG}", "type": "mapped_to"},
                    {"file": "crosswalk.csv", "from": "MDG:{MDG}", "to": "S4:{S4}", "type": "replicated_to"},
                ],
            }
            model = build_model(manifest, base)
            self.assertEqual(len(model["nodes"]), 3)
            self.assertEqual(len(model["relationships"]), 2)
            self.assertTrue(analyze(model)["valid"])
            self.assertEqual(shortest_path(model, "AFS:4711", "S4:10000345"), ["AFS:4711", "MDG:7200311", "S4:10000345"])
            self.assertEqual(model["nodes"][0]["provenance"], [{"file": "crosswalk.csv", "row": 2}])
            self.assertEqual(model["relationships"][0]["provenance"], {"file": "crosswalk.csv", "row": 2})

    def test_same_node_merges_provenance_and_exposes_attribute_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "a.csv").write_text("ID,LABEL\n1,Customer One\n", encoding="utf-8")
            (base / "b.csv").write_text("ID,LABEL\n1,Customer 1\n", encoding="utf-8")
            manifest = {"node_sources": [
                {"file": "a.csv", "id": "S4:{ID}", "system": "S4", "object": "customer", "label": "{LABEL}"},
                {"file": "b.csv", "id": "S4:{ID}", "system": "S4", "object": "customer", "label": "{LABEL}"},
            ]}
            model = build_model(manifest, base)
            self.assertEqual(len(model["nodes"]), 1)
            node = model["nodes"][0]
            self.assertEqual(node["provenance"], [{"file": "a.csv", "row": 2}, {"file": "b.csv", "row": 2}])
            self.assertEqual(node["conflicts"]["label"], ["Customer 1", "Customer One"])

    def test_missing_template_column_is_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "source.csv").write_text("ID\n1\n", encoding="utf-8")
            manifest = {"node_sources": [{"file": "source.csv", "id": "X:{MISSING}"}]}
            with self.assertRaisesRegex(ValueError, "missing CSV column"):
                build_model(manifest, base)


if __name__ == "__main__":
    unittest.main()
