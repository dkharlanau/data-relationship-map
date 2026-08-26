import unittest

from relationship_diff import compare


class RelationshipDiffTests(unittest.TestCase):
    def test_relationship_and_orphan_drift(self):
        before = {
            "nodes": [
                {"id": "A", "system": "legacy", "label": "Old A"},
                {"id": "B", "system": "target"},
                {"id": "C", "system": "target"},
            ],
            "relationships": [{"from": "A", "to": "B", "type": "maps_to"}],
        }
        after = {
            "nodes": [
                {"id": "A", "system": "legacy", "label": "A"},
                {"id": "B", "system": "target"},
                {"id": "C", "system": "target"},
                {"id": "D", "system": "target"},
            ],
            "relationships": [
                {"from": "A", "to": "B", "type": "maps_to"},
                {"from": "B", "to": "C", "type": "links_to"},
            ],
        }
        result = compare(before, after)
        self.assertEqual(result["added_nodes"], ["D"])
        self.assertEqual(result["removed_nodes"], [])
        self.assertEqual(result["changed_nodes"], [{
            "id": "A",
            "before": {"system": "legacy", "label": "Old A"},
            "after": {"system": "legacy", "label": "A"},
        }])
        self.assertEqual(result["added_relationships"], [{"from": "B", "type": "links_to", "to": "C"}])
        self.assertEqual(result["resolved_orphans"], ["C"])
        self.assertEqual(result["new_orphans"], ["D"])

    def test_removed_relationship_creates_orphan(self):
        before = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "relationships": [{"from": "A", "to": "B", "type": "links_to"}],
        }
        after = {"nodes": [{"id": "A"}, {"id": "B"}], "relationships": []}
        result = compare(before, after)
        self.assertEqual(result["removed_relationships"], [{"from": "A", "type": "links_to", "to": "B"}])
        self.assertEqual(result["new_orphans"], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
