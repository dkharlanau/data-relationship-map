"""Configuration errors must not become clean-looking investigation evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import unittest

from relationship_artifacts import build_index
from relationship_handoff import build_handoff
from relationship_investigation import build_investigation
from relationship_policy import PolicyValidationError, evaluate, load_policy

ROOT = Path(__file__).resolve().parents[1]
MODEL = {"nodes": [{"id": "ERP:100:0001"}, {"id": "MDG:100:0001"}, {"id": "MDG:100:0002"}],
         "relationships": [{"from": "ERP:100:0001", "to": target, "type": "mapped_to"}
                           for target in ("MDG:100:0001", "MDG:100:0002")]}


class PolicyContractTests(unittest.TestCase):
    def test_policy_root_and_unknown_fields(self):
        for policy in (None, [], 0, "private-value", {"relationship_rule": {}}, {3: True}):
            with self.subTest(policy=policy), self.assertRaises(PolicyValidationError):
                evaluate(MODEL, policy)

    def test_rules_shape(self):
        for rules in (None, [], True, 0, "private-value"):
            with self.subTest(rules=rules), self.assertRaises(PolicyValidationError):
                evaluate(MODEL, {"relationship_rules": rules})

    def test_rule_names_and_bodies(self):
        for rules in ({"": {}}, {"  ": {}}, {1: {}}, {"mapped_to": []}, {"mapped_to": None},
                      {"mapped_to": {"max_outgiong": 1}}, {"mapped_to": {"PRIVATE_FIELD": "PRIVATE_VALUE"}}):
            with self.subTest(rules=rules), self.assertRaises(PolicyValidationError) as caught:
                evaluate(MODEL, {"relationship_rules": rules})
            self.assertNotIn("PRIVATE", str(caught.exception))

    def test_noninteger_or_negative_limits_rejected(self):
        for key in ("max_incoming", "max_outgoing"):
            for value in (True, False, -1, 1.0, 1.9, "1", [], {}, float('nan'), float('inf')):
                with self.subTest(key=key, value=value), self.assertRaises(PolicyValidationError):
                    evaluate(MODEL, {"relationship_rules": {"mapped_to": {key: value}}})

    def test_collision_flags_require_booleans(self):
        for key in ("report_identity_collisions", "fail_on_identity_collisions"):
            for value in (None, 0, 1, "false", [], {}):
                with self.subTest(key=key, value=value), self.assertRaises(PolicyValidationError):
                    evaluate(MODEL, {key: value})

    def test_valid_empty_null_and_zero_limits(self):
        for policy in ({}, {"relationship_rules": {}}, {"relationship_rules": {"mapped_to": {}}},
                       {"relationship_rules": {"mapped_to": {"max_outgoing": None, "max_incoming": None}}}):
            self.assertTrue(evaluate(MODEL, policy)["passed"])
        zero = evaluate(MODEL, {"relationship_rules": {"mapped_to": {"max_outgoing": 0}}})
        self.assertFalse(zero['passed'])
        self.assertEqual(zero['cardinality_violations'][0]['maximum'], 0)
        one = evaluate(MODEL, {"relationship_rules": {"mapped_to": {"max_outgoing": 1}}})
        self.assertEqual(one['cardinality_violations'][0]['actual'], 2)

    def test_legacy_collision_flag_combinations(self):
        model = {"nodes": [{"id": "A", "identity_collisions": ["01", "1"]}], "relationships": []}
        self.assertFalse(evaluate(model, {})['passed'])
        for report in (False, True):
            for fail in (False, True):
                result = evaluate(model, {"report_identity_collisions": report, "fail_on_identity_collisions": fail})
                self.assertEqual(result['passed'], not (report and fail))
                self.assertEqual(len(result['identity_collisions']), int(report))

    def test_no_normalization_mutation_or_new_default_rules(self):
        policy = {"relationship_rules": {" mapped_to ": {"max_outgoing": 0}}}
        before = copy.deepcopy((MODEL, policy))
        first = evaluate(MODEL, policy)
        self.assertTrue(first['passed'])  # exact type names, not guessed or trimmed
        self.assertEqual(first, evaluate(MODEL, policy))
        self.assertEqual((MODEL, policy), before)

    def test_strict_json_duplicate_members(self):
        texts = ['{"relationship_rules":{},"relationship_rules":{}}',
                 '{"relationship_rules":{"mapped_to":{},"mapped_to":{}}}',
                 '{"relationship_rules":{"mapped_to":{"max_outgoing":1,"max_\\u006futgoing":2}}}']
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'policy.json'
            for text in texts:
                file.write_text(text)
                with self.subTest(text=text), self.assertRaisesRegex(PolicyValidationError, 'repeated members'):
                    load_policy(file)

    def test_strict_json_nonfinite_and_invalid_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'policy.json'
            for value in ('NaN', 'Infinity', '-Infinity', '1e999'):
                file.write_text('{"relationship_rules":{"mapped_to":{"max_outgoing":'+value+'}}}')
                with self.subTest(value=value), self.assertRaises(PolicyValidationError):
                    load_policy(file)
            for data in (b'{"PRIVATE_VALUE":', b'\xff', b'[]'):
                file.write_bytes(data)
                with self.assertRaises(PolicyValidationError) as caught:
                    load_policy(file)
                self.assertNotIn('PRIVATE', str(caught.exception))

    def test_unreadable_policy_fixed_error(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(PolicyValidationError) as caught:
            load_policy(Path(tmp)/'PRIVATE_PATH')
        self.assertNotIn('PRIVATE', str(caught.exception))

    def test_api_formatted_traceback_suppresses_parser_and_io_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'PRIVATE_PATH'
            for data in (None, b'{"PRIVATE_VALUE":', b'\xffPRIVATE_VALUE'):
                if data is not None:
                    file.write_bytes(data)
                try:
                    load_policy(file)
                except PolicyValidationError as exc:
                    rendered = ''.join(traceback.format_exception(exc))
                    self.assertNotIn('PRIVATE_PATH', rendered)
                    self.assertNotIn('PRIVATE_VALUE', rendered)
                    self.assertNotIn('JSONDecodeError:', rendered)
                    self.assertNotIn('UnicodeDecodeError:', rendered)
                    self.assertNotIn('FileNotFoundError:', rendered)
                else:
                    self.fail('invalid policy accepted')

    def test_direct_consumers_stop_before_handoff_creation_or_overwrite(self):
        invalid = {"relationship_rules": []}
        for function in (evaluate, build_index):
            with self.assertRaises(PolicyValidationError):
                function(MODEL, invalid)
        with self.assertRaises(PolicyValidationError):
            build_investigation(MODEL, policy=invalid)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'handoff'
            with self.assertRaises(PolicyValidationError):
                build_handoff(MODEL, folder, focus='ERP:100:0001', policy=invalid)
            self.assertFalse(folder.exists())
            folder.mkdir(); (folder/'manifest.json').write_text('retained')
            with self.assertRaises(PolicyValidationError):
                build_handoff(MODEL, folder, focus='ERP:100:0001', policy=invalid)
            self.assertEqual((folder/'manifest.json').read_text(), 'retained')
            self.assertEqual(len(list(folder.iterdir())), 1)

    def test_all_module_and_dispatcher_clis_stop_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); model = base/'model.json'; model.write_text(json.dumps(MODEL))
            policy = base/'policy.json'; policy.write_text('{"PRIVATE_FIELD":"PRIVATE_VALUE"}')
            commands = [('policy', 'relationship_policy.py', [str(model),str(policy)]),
                        ('investigate', 'relationship_investigation.py', [str(model),'--policy',str(policy),
                         '--json-output',str(base/'result.json'),'--markdown',str(base/'result.md'),'--html',str(base/'result.html')]),
                        ('artifacts', 'relationship_artifacts.py', [str(model),'--policy',str(policy),'--output',str(base/'index.json')]),
                        ('handoff', 'relationship_handoff.py', ['build',str(model),str(base/'handoff'),'--policy',str(policy),'--focus','ERP:100:0001'])]
            outputs = [base/name for name in ('result.json','result.md','result.html','index.json')]
            for existing in (False, True):
                if existing:
                    for path in outputs: path.write_text('retained')
                    (base/'handoff').mkdir(); (base/'handoff'/'manifest.json').write_text('retained')
                for command,module,args in commands:
                    for prefix in ([sys.executable,'-B',str(ROOT/module)], [sys.executable,'-B',str(ROOT/'drm_cli.py'),command]):
                        with self.subTest(command=command, existing=existing, prefix=prefix):
                            result = subprocess.run([*prefix,*args],capture_output=True,text=True)
                            self.assertEqual(result.returncode,2,result.stderr)
                            self.assertEqual(result.stdout,'')
                            self.assertNotIn('Traceback',result.stderr)
                            self.assertNotIn('PRIVATE',result.stderr)
                            for path in outputs:
                                self.assertEqual(path.read_text() if path.exists() else None,'retained' if existing else None)
                            handoff=base/'handoff'
                            self.assertEqual(handoff.exists(),existing)
                            if existing:
                                self.assertEqual([p.name for p in handoff.iterdir()],['manifest.json'])
                                self.assertEqual((handoff/'manifest.json').read_text(),'retained')

    def test_valid_policy_failure_still_returns_findings_exit_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); model=base/'model.json'; model.write_text(json.dumps(MODEL))
            policy=base/'policy.json'; policy.write_text('{"relationship_rules":{"mapped_to":{"max_outgoing":1}}}')
            result=subprocess.run([sys.executable,'-B',str(ROOT/'drm_cli.py'),'policy',str(model),str(policy)],capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertFalse(json.loads(result.stdout)['passed'])
            self.assertEqual(result.stderr,'')


if __name__ == '__main__':
    unittest.main()
