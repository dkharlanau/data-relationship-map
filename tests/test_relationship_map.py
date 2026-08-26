import unittest

from relationship_map import analyze, shortest_path


class RelationshipMapTests(unittest.TestCase):
    def setUp(self):
        self.model = {
            "nodes": [
                {"id": "A"},
                {"id": "B"},
                {"id": "C"},
                {"id": "ORPHAN"},
            ],
            "relationships": [
                {"from": "A", "to": "B", "type": "maps_to"},
                {"from": "B", "to": "C", "type": "replicates_to"},
            ],
        }

    def test_valid_graph_with_orphan(self):
        result = analyze(self.model)
        self.assertTrue(result["valid"])
        self.assertEqual(result["orphans"], ["ORPHAN"])

    def test_broken_relationship(self):
        model = dict(self.model)
        model["relationships"] = self.model["relationships"] + [
            {"from": "C", "to": "MISSING", "type": "links_to"}
        ]
        result = analyze(model)
        self.assertFalse(result["valid"])
        self.assertEqual(result["broken_relationships"][0]["missing"], ["MISSING"])

    def test_path(self):
        self.assertEqual(shortest_path(self.model, "A", "C"), ["A", "B", "C"])
        self.assertEqual(shortest_path(self.model, "A", "ORPHAN"), [])


if __name__ == "__main__":
    unittest.main()
