import unittest

from relationship_artifacts import artifact_ref, build_index, normalize_observed_at


class RelationshipArtifactTests(unittest.TestCase):
    def setUp(self):
        self.model = {
            "nodes": [
                {"id": "AFS:4711", "system": "AFS", "object": "customer", "provenance": [{"file": "crosswalk.xlsx", "sheet": "Data", "row": 2}]},
                {"id": "MDG:7200311", "system": "MDG", "object": "business-partner"},
                {"id": "S4:10000345", "system": "S4", "object": "business-partner"},
            ],
            "relationships": [
                {"from": "AFS:4711", "to": "MDG:7200311", "type": "mapped_to", "provenance": {"file": "crosswalk.xlsx", "row": 2}},
                {"from": "MDG:7200311", "to": "S4:10000345", "type": "replicated_to"},
            ],
        }

    def test_object_and_relationship_refs_are_stable(self):
        index = build_index(self.model)
        objects = {item["id"]: item for item in index["objects"]}
        self.assertEqual(objects["AFS:4711"]["artifact_ref"], "eac://dkharlanau/data-relationship-map/object/AFS:4711")
        relation = next(item for item in index["relationships"] if item["type"] == "mapped_to")
        self.assertEqual(relation["artifact_ref"], "eac://dkharlanau/data-relationship-map/relationship/AFS:4711/mapped_to/MDG:7200311")
        self.assertEqual(relation["from_ref"], objects["AFS:4711"]["artifact_ref"])
        self.assertEqual(relation["to_ref"], objects["MDG:7200311"]["artifact_ref"])

    def test_observed_at_is_explicit_and_canonicalized(self):
        index = build_index(self.model, observed_at="2026-08-25T12:00:00+02:00")
        self.assertEqual(index["observed_at"], "2026-08-25T10:00:00Z")

    def test_model_observed_at_is_used_when_call_does_not_override_it(self):
        model = {**self.model, "observed_at": "2026-08-25T10:00:00Z"}
        index = build_index(model)
        self.assertEqual(index["observed_at"], "2026-08-25T10:00:00Z")

    def test_call_observed_at_overrides_model_value(self):
        model = {**self.model, "observed_at": "2026-08-20T10:00:00Z"}
        index = build_index(model, observed_at="2026-08-25T10:00:00Z")
        self.assertEqual(index["observed_at"], "2026-08-25T10:00:00Z")

    def test_missing_observed_at_remains_backward_compatible(self):
        index = build_index(self.model)
        self.assertNotIn("observed_at", index)

    def test_naive_observed_at_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            build_index(self.model, observed_at="2026-08-25T10:00:00")

    def test_invalid_observed_at_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ISO-8601"):
            normalize_observed_at("not-a-time")

    def test_source_location_remains_provenance_not_identity(self):
        first = build_index(self.model)
        changed = {
            "nodes": [dict(node) for node in self.model["nodes"]],
            "relationships": [dict(rel) for rel in self.model["relationships"]],
        }
        changed["nodes"][0]["provenance"] = [{"file": "moved.xlsx", "sheet": "Other", "row": 99}]
        second = build_index(changed)
        self.assertEqual(first["objects"][0]["artifact_ref"], second["objects"][0]["artifact_ref"])
        self.assertNotEqual(first["objects"][0]["provenance"], second["objects"][0]["provenance"])

    def test_cardinality_finding_has_deterministic_ref(self):
        model = {
            "nodes": self.model["nodes"] + [{"id": "MDG:999", "system": "MDG", "object": "business-partner"}],
            "relationships": [
                {"from": "AFS:4711", "to": "MDG:7200311", "type": "mapped_to"},
                {"from": "AFS:4711", "to": "MDG:999", "type": "mapped_to"},
            ],
        }
        policy = {"relationship_rules": {"mapped_to": {"max_outgoing": 1, "max_incoming": 1}}}
        index = build_index(model, policy)
        self.assertTrue(index["valid"])
        self.assertFalse(index["policy_passed"])
        finding = index["findings"][0]
        self.assertEqual(finding["artifact_ref"], "eac://dkharlanau/data-relationship-map/finding/cardinality/mapped_to/outgoing/AFS:4711")
        self.assertEqual(finding["node_ref"], "eac://dkharlanau/data-relationship-map/object/AFS:4711")
        self.assertEqual(finding["related"], ["MDG:7200311", "MDG:999"])

    def test_identity_collision_finding_ref(self):
        model = {
            "nodes": [
                {"id": "S4:4711", "system": "S4", "object": "customer", "identity_collisions": ["S4:0004711", "S4:4711"], "provenance": [{"row": 2}, {"row": 3}]}
            ],
            "relationships": []
        }
        index = build_index(model, {"report_identity_collisions": True, "fail_on_identity_collisions": True})
        finding = index["findings"][0]
        self.assertEqual(finding["artifact_ref"], "eac://dkharlanau/data-relationship-map/finding/identity-collision/S4:4711")
        self.assertEqual(finding["severity"], "error")
        self.assertFalse(index["policy_passed"])

    def test_input_order_does_not_change_index(self):
        reordered = {
            "nodes": list(reversed(self.model["nodes"])),
            "relationships": list(reversed(self.model["relationships"])),
        }
        self.assertEqual(build_index(self.model), build_index(reordered))

    def test_invalid_graph_produces_invalid_index(self):
        invalid = {
            "nodes": [{"id": "A", "system": "X", "object": "customer"}],
            "relationships": [{"from": "A", "to": "MISSING", "type": "mapped_to"}],
        }
        index = build_index(invalid)
        self.assertFalse(index["valid"])
        self.assertTrue(index["validation"]["broken_references"])

    def test_ref_percent_encodes_slash(self):
        self.assertEqual(
            artifact_ref("object", "S4:customer/1000"),
            "eac://dkharlanau/data-relationship-map/object/S4:customer%2F1000"
        )


if __name__ == "__main__":
    unittest.main()