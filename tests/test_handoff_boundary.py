"""Generated synthetic cases for the read-only verifier boundary."""
import hashlib
import json
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from relationship_handoff import PACK_FILES, build_handoff, verify_handoff


class HandoffBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pack = self.root / 'pack'
        self.manifest = build_handoff(
            {'nodes': [{'id': 'S4:SYNTHETIC', 'system': 'S4', 'object': 'customer'}],
             'relationships': []}, self.pack, focus='S4:SYNTHETIC')

    def save(self):
        (self.pack / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def payload(self, name, data):
        (self.pack / name).write_bytes(data)
        self.manifest['files'][name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        self.save()

    def invalid(self):
        result = verify_handoff(self.pack)
        self.assertIs(result['valid'], False)
        self.assertTrue(result['errors'])
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))
        return result

    def legacy(self, explicit=True):
        self.manifest['schema_version'] = '0.1'
        self.manifest['files'].pop('artifact-index.json')
        data = {k: json.loads((self.pack / f).read_text()) for k, f in
                [('graph', 'graph.json'), ('investigation', 'investigation.json')]}
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        self.manifest['pack_id'] = 'relationship-handoff-' + hashlib.sha256(raw).hexdigest()[:24]
        if not explicit:
            self.manifest.pop('schema_version')
        self.save()

    def test_valid_v02(self):
        self.assertTrue(verify_handoff(self.pack)['valid'])

    def test_valid_v01(self):
        self.legacy()
        self.assertTrue(verify_handoff(self.pack)['valid'])

    def test_valid_implicit_v01(self):
        self.legacy(False)
        self.assertTrue(verify_handoff(self.pack)['valid'])

    def test_manifest_non_object(self):
        for value in [None, [], 1, True, 'PRIVATE_SENTINEL']:
            (self.pack / 'manifest.json').write_text(json.dumps(value))
            self.invalid()

    def test_files_non_object(self):
        for value in [None, [], 1, True, 'PRIVATE_SENTINEL']:
            self.manifest['files'] = value
            self.save()
            self.invalid()

    def test_missing_files(self):
        self.manifest.pop('files')
        self.save()
        self.invalid()

    def test_empty_files(self):
        self.manifest['files'] = {}
        self.save()
        self.invalid()

    def test_truncated_files(self):
        self.manifest['files'].pop('investigation.md')
        self.save()
        self.invalid()

    def test_extra_path_refused_without_read(self):
        self.manifest['files']['../PRIVATE_SENTINEL'] = {'bytes': 0, 'sha256': '0' * 64}
        self.save()
        import relationship_handoff
        with patch.object(relationship_handoff, '_read_regular_bytes', wraps=relationship_handoff._read_regular_bytes) as reader:
            self.invalid()
        self.assertEqual(reader.call_count, 1)

    def test_entry_non_object(self):
        for value in [None, [], 1, True, 'PRIVATE_SENTINEL']:
            self.manifest['files']['graph.json'] = value
            self.save()
            self.invalid()

    def test_invalid_digest(self):
        for value in [None, [], 1, 'A' * 64, '0' * 63, 'PRIVATE_SENTINEL']:
            self.manifest['files']['graph.json']['sha256'] = value
            self.save()
            self.invalid()

    def test_invalid_byte_count(self):
        for value in [None, False, True, -1, 1.0, '1', [], {}]:
            self.manifest['files']['graph.json']['bytes'] = value
            self.save()
            self.invalid()

    def test_invalid_pack_id_not_echoed(self):
        for value in [None, [], True, 'PRIVATE_SENTINEL', 'relationship-handoff-' + 'G' * 24]:
            self.manifest['pack_id'] = value
            self.save()
            self.assertIsNone(self.invalid()['pack_id'])

    def test_schema_not_coerced_or_echoed(self):
        for value in [None, 0.2, [], {}, 'PRIVATE_SENTINEL']:
            self.manifest['schema_version'] = value
            self.save()
            self.invalid()

    def test_duplicate_manifest_member(self):
        for extra in ['"files": {},', '"f\\u0069les": {},', '"schema_version": "0.2",']:
            self.save()
            text = (self.pack / 'manifest.json').read_text()
            (self.pack / 'manifest.json').write_text('{' + extra + text[1:])
            self.invalid()

    def test_nonfinite_manifest(self):
        for token in ['NaN', 'Infinity', '-Infinity', '1e999']:
            self.save()
            text = (self.pack / 'manifest.json').read_text()
            (self.pack / 'manifest.json').write_text('{"extra":' + token + ',' + text[1:])
            self.invalid()

    def test_malformed_manifest_json_utf8(self):
        for data in [b'{', b'\xff', b'{"x":"\xff"}', b'']:
            (self.pack / 'manifest.json').write_bytes(data)
            self.invalid()

    def test_missing_manifest(self):
        (self.pack / 'manifest.json').unlink()
        self.invalid()

    def test_manifest_symlink(self):
        outside = self.root / 'PRIVATE_SENTINEL'
        (self.pack / 'manifest.json').rename(outside)
        (self.pack / 'manifest.json').symlink_to(outside)
        self.invalid()

    def test_payload_symlink(self):
        outside = self.root / 'PRIVATE_SENTINEL'
        (self.pack / 'graph.json').rename(outside)
        (self.pack / 'graph.json').symlink_to(outside)
        self.invalid()

    def test_payload_directory(self):
        (self.pack / 'graph.json').unlink()
        (self.pack / 'graph.json').mkdir()
        self.invalid()

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO unavailable')
    def test_fifo_refused_before_open(self):
        (self.pack / 'graph.json').unlink()
        os.mkfifo(self.pack / 'graph.json')
        self.invalid()

    def test_missing_payload(self):
        (self.pack / 'graph.json').unlink()
        self.invalid()

    def test_payload_read_error_not_echoed(self):
        original = Path.read_bytes
        def read(path):
            if path.name == 'graph.json':
                raise PermissionError('PRIVATE_SENTINEL')
            return original(path)
        with patch.object(Path, 'read_bytes', read):
            self.invalid()

    def test_duplicate_semantic_members_despite_rehash(self):
        for name in ['graph.json', 'investigation.json', 'artifact-index.json']:
            old = (self.pack / name).read_bytes()
            self.payload(name, b'{"a":1,"\\u0061":1}')
            self.assertIn({'kind': 'invalid_payload', 'file': name}, self.invalid()['errors'])
            self.payload(name, old)

    def test_nonfinite_semantics_despite_rehash(self):
        for name in ['graph.json', 'investigation.json', 'artifact-index.json']:
            old = (self.pack / name).read_bytes()
            for token in ['NaN', 'Infinity', '-Infinity', '1e999']:
                self.payload(name, ('{"v":' + token + '}').encode())
                self.assertIn({'kind': 'invalid_payload', 'file': name}, self.invalid()['errors'])
            self.payload(name, old)

    def test_semantic_object_required(self):
        for name in ['graph.json', 'investigation.json', 'artifact-index.json']:
            old = (self.pack / name).read_bytes()
            for data in [b'[]', b'null', b'42']:
                self.payload(name, data)
                self.invalid()
            self.payload(name, old)

    def test_payload_encoding_surrogate(self):
        for data in [b'\xff', b'{', b'{"value":"\\ud800"}']:
            self.payload('graph.json', data)
            self.invalid()

    def test_deep_manifest_refused(self):
        (self.pack / 'manifest.json').write_text('{"v":' + '[' * 2000 + '0' + ']' * 2000 + '}')
        self.invalid()

    def test_deep_payload_refused(self):
        self.payload('graph.json', ('{"v":' + '[' * 2000 + '0' + ']' * 2000 + '}').encode())
        self.invalid()

    def test_single_read_no_writes(self):
        paths = [self.pack / 'manifest.json', *(self.pack / x for x in PACK_FILES)]
        before = {p.name: p.read_bytes() for p in paths}
        counts = Counter()
        original = Path.read_bytes
        def read(path):
            counts[path.name] += 1
            return original(path)
        with patch.object(Path, 'read_bytes', read), patch.object(Path, 'write_bytes', side_effect=AssertionError), patch.object(Path, 'write_text', side_effect=AssertionError):
            self.assertTrue(verify_handoff(self.pack)['valid'])
        self.assertEqual(counts, Counter({p.name: 1 for p in paths}))
        self.assertEqual(before, {p.name: p.read_bytes() for p in paths})

    def test_manifest_metadata_not_replayed(self):
        self.manifest['status'] = 'invented'
        self.manifest['summary'] = {'nodes': -1}
        self.save()
        self.assertTrue(verify_handoff(self.pack)['valid'])


if __name__ == '__main__':
    unittest.main()
