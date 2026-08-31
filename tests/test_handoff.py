import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from relationship_handoff import build_handoff, verify_handoff


class RelationshipHandoffTests(unittest.TestCase):
    def setUp(self):
        self.model = {
            "observed_at": "2026-08-25T10:00:00Z",
            "nodes": [
                {"id": "LEGACY:1", "system": "LEGACY", "object": "customer"},
                {"id": "MDG:1", "system": "MDG", "object": "business-partner"},
                {"id": "S4:1", "system": "S4", "object": "customer"},
                {"id": "UNRELATED:1", "system": "CRM", "object": "contact"},
            ],
            "relationships": [
                {"from": "LEGACY:1", "to": "MDG:1", "type": "mapped_to"},
                {"from": "MDG:1", "to": "S4:1", "type": "replicated_to"},
            ],
        }
        self.policy = {
            "relationship_rules": {"mapped_to": {"max_outgoing": 1, "max_incoming": 1}}
        }

    def test_builds_bounded_integrity_checkable_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_handoff(
                self.model,
                tmp,
                focus="MDG:1",
                policy=self.policy,
                max_depth=1,
                observed_at="2026-08-25T12:00:00+02:00",
            )
            self.assertTrue(manifest["pack_id"].startswith("relationship-handoff-"))
            self.assertEqual(manifest["summary"]["nodes"], 3)
            graph = json.loads(Path(tmp, "graph.json").read_text(encoding="utf-8"))
            self.assertEqual([node["id"] for node in graph["nodes"]], ["LEGACY:1", "MDG:1", "S4:1"])
            self.assertNotIn("UNRELATED:1", json.dumps(graph))
            investigation = json.loads(Path(tmp, "investigation.json").read_text(encoding="utf-8"))
            self.assertEqual(investigation["status"], "clear")
            self.assertNotIn("UNRELATED:1", json.dumps(investigation))
            artifact_index = json.loads(Path(tmp, "artifact-index.json").read_text(encoding="utf-8"))
            self.assertEqual(artifact_index["observed_at"], "2026-08-25T10:00:00Z")
            self.assertEqual(len(artifact_index["objects"]), 3)
            self.assertNotIn("UNRELATED:1", json.dumps(artifact_index))
            self.assertEqual(manifest["schema_version"], "0.2")
            self.assertEqual(manifest["observed_at"], "2026-08-25T10:00:00Z")
            self.assertTrue(Path(tmp, "investigation.html").is_file())
            self.assertTrue(verify_handoff(tmp)["valid"])

    def test_same_semantics_produce_same_pack_id(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = build_handoff(self.model, first, focus="MDG:1", policy=self.policy)
            two = build_handoff(self.model, second, focus="MDG:1", policy=self.policy)
            self.assertEqual(one["pack_id"], two["pack_id"])

    def test_tamper_breaks_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_handoff(self.model, tmp, focus="MDG:1", policy=self.policy)
            Path(tmp, "graph.json").write_text("{}\n", encoding="utf-8")
            result = verify_handoff(tmp)
            self.assertFalse(result["valid"])
            self.assertTrue(any(error["kind"] == "sha256_mismatch" for error in result["errors"]))

    def test_artifact_index_tamper_breaks_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_handoff(self.model, tmp, focus="MDG:1", policy=self.policy)
            Path(tmp, "artifact-index.json").write_text("{}\n", encoding="utf-8")
            result = verify_handoff(tmp)
            self.assertFalse(result["valid"])
            self.assertTrue(any(error["file"] == "artifact-index.json" for error in result["errors"]))

    def test_legacy_v01_pack_remains_verifiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_handoff(self.model, tmp, focus="MDG:1", policy=self.policy)
            root = Path(tmp)
            graph = json.loads((root / "graph.json").read_text(encoding="utf-8"))
            investigation = json.loads((root / "investigation.json").read_text(encoding="utf-8"))
            canonical = json.dumps(
                {"graph": graph, "investigation": investigation},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            manifest["schema_version"] = "0.1"
            manifest["pack_id"] = "relationship-handoff-" + hashlib.sha256(canonical).hexdigest()[:24]
            manifest["files"].pop("artifact-index.json")
            (root / "artifact-index.json").unlink()
            (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.assertTrue(verify_handoff(tmp)["valid"])

    def test_missing_focus_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_handoff(self.model, tmp, focus="MISSING", policy=self.policy)


if __name__ == "__main__":
    unittest.main()
