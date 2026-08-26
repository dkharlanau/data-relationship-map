import unittest

from relationship_policy import evaluate


class RelationshipPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "relationship_rules": {
                "mapped_to": {"max_outgoing": 1, "max_incoming": 1}
            },
            "fail_on_identity_collisions": True,
        }

    def test_one_to_one_relationship_passes(self):
        model = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "relationships": [{"from": "A", "to": "B", "type": "mapped_to"}],
        }
        self.assertTrue(evaluate(model, self.policy)["passed"])

    def test_one_to_many_and_many_to_one_are_reported(self):
        model = {
            "nodes": [{"id": "A1"}, {"id": "A2"}, {"id": "B1"}, {"id": "B2"}],
            "relationships": [
                {"from": "A1", "to": "B1", "type": "mapped_to"},
                {"from": "A1", "to": "B2", "type": "mapped_to"},
                {"from": "A2", "to": "B1", "type": "mapped_to"},
            ],
        }
        result = evaluate(model, self.policy)
        self.assertFalse(result["passed"])
        self.assertEqual(result["cardinality_violations"], [
            {
                "kind": "outgoing_cardinality",
                "relationship_type": "mapped_to",
                "node": "A1",
                "actual": 2,
                "maximum": 1,
                "related_ids": ["B1", "B2"],
            },
            {
                "kind": "incoming_cardinality",
                "relationship_type": "mapped_to",
                "node": "B1",
                "actual": 2,
                "maximum": 1,
                "related_ids": ["A1", "A2"],
            },
        ])

    def test_unrestricted_relationship_type_is_ignored(self):
        model = {
            "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
            "relationships": [
                {"from": "A", "to": "B", "type": "ship_to"},
                {"from": "A", "to": "C", "type": "ship_to"},
            ],
        }
        self.assertTrue(evaluate(model, self.policy)["passed"])

    def test_identity_collision_can_fail_policy(self):
        model = {
            "nodes": [{"id": "S4:4711", "identity_collisions": ["S4:0004711", "S4:4711"]}],
            "relationships": [],
        }
        result = evaluate(model, self.policy)
        self.assertFalse(result["passed"])
        self.assertEqual(result["identity_collisions"], [
            {"node": "S4:4711", "raw_identities": ["S4:0004711", "S4:4711"]}
        ])
        self.assertIn("identity_collisions", result["failed_checks"])

    def test_collision_can_be_report_only(self):
        policy = dict(self.policy, fail_on_identity_collisions=False)
        model = {
            "nodes": [{"id": "S4:4711", "identity_collisions": ["S4:0004711", "S4:4711"]}],
            "relationships": [],
        }
        result = evaluate(model, policy)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["identity_collisions"]), 1)


if __name__ == "__main__":
    unittest.main()
