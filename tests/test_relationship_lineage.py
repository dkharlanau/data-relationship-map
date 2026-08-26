import unittest

from relationship_lineage import traverse


class RelationshipLineageTests(unittest.TestCase):
    def setUp(self):
        self.model = {
            "nodes": [
                {"id": "AFS:1", "system": "AFS", "object": "customer"},
                {"id": "MDG:2", "system": "MDG", "object": "business-partner"},
                {"id": "S4:3", "system": "S4", "object": "business-partner"},
                {"id": "S4:4", "system": "S4", "object": "customer"},
            ],
            "relationships": [
                {"from": "AFS:1", "to": "MDG:2", "type": "mapped_to", "provenance": {"row": 2}},
                {"from": "MDG:2", "to": "S4:3", "type": "replicated_to"},
                {"from": "S4:3", "to": "S4:4", "type": "ship_to"},
            ],
        }

    def test_downstream_follows_direction_only(self):
        result = traverse(self.model, "AFS:1", "downstream")
        self.assertEqual([item["id"] for item in result["reached"]], ["AFS:1", "MDG:2", "S4:3", "S4:4"])
        self.assertEqual(result["paths"]["S4:4"], ["AFS:1", "MDG:2", "S4:3", "S4:4"])
        reverse = traverse(self.model, "S4:4", "downstream")
        self.assertEqual([item["id"] for item in reverse["reached"]], ["S4:4"])

    def test_upstream_reverses_relationship_direction(self):
        result = traverse(self.model, "S4:4", "upstream")
        self.assertEqual([item["id"] for item in result["reached"]], ["S4:4", "S4:3", "MDG:2", "AFS:1"])
        self.assertEqual(result["paths"]["AFS:1"], ["S4:4", "S4:3", "MDG:2", "AFS:1"])

    def test_stop_system_includes_boundary_but_does_not_cross_it(self):
        result = traverse(self.model, "AFS:1", "downstream", stop_systems={"MDG"})
        self.assertEqual([item["id"] for item in result["reached"]], ["AFS:1", "MDG:2"])
        self.assertEqual(result["boundaries"][0]["id"], "MDG:2")

    def test_max_depth(self):
        result = traverse(self.model, "AFS:1", "downstream", max_depth=1)
        self.assertEqual([item["id"] for item in result["reached"]], ["AFS:1", "MDG:2"])

    def test_provenance_preserved_on_edges(self):
        result = traverse(self.model, "AFS:1", "downstream", max_depth=1)
        self.assertEqual(result["edges"][0]["provenance"], {"row": 2})

    def test_unknown_start(self):
        result = traverse(self.model, "MISSING")
        self.assertFalse(result["valid_start"])
        self.assertEqual(result["reached"], [])


if __name__ == "__main__":
    unittest.main()
