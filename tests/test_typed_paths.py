import copy
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import tempfile
import unittest

from csv_adapter import build_model
from drm_cli import main
from relationship_map import shortest_path, analyze
from relationship_policy import evaluate

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/bp-connection-paths'
A, B, C, D = 'LEGACY:100:0004711', 'MDG:100:0009001', 'S4:100:0008001', 'S4:100:0008002'
CROSSWALK, PARTNER = 'explicit_crosswalk', 'ship_to_in_sales_area:1000:10:00'


class TypedPathTests(unittest.TestCase):
    def setUp(self):
        self.model = build_model(json.loads((EXAMPLE / 'manifest.json').read_text()), EXAMPLE)

    def test_unrestricted_path_keeps_partner_connection(self):
        self.assertEqual(shortest_path(self.model, A, C), [A, B, C])

    def test_explicit_crosswalk_does_not_traverse_partner_edge(self):
        self.assertEqual(shortest_path(self.model, A, B, relation_types=[CROSSWALK]), [A, B])
        self.assertEqual(shortest_path(self.model, A, C, relation_types=[CROSSWALK]), [])

    def test_multiple_types_are_alternatives_not_required_path_sequence(self):
        self.assertEqual(shortest_path(self.model, A, C, relation_types=[PARTNER, CROSSWALK]), [A, B, C])
        self.assertEqual(shortest_path(self.model, A, B, relation_types=[PARTNER, CROSSWALK]), [A, B])

    def test_paths_are_symmetric_not_directional_lineage(self):
        self.assertEqual(shortest_path(self.model, C, A, relation_types=[CROSSWALK, PARTNER]), [C, B, A])

    def test_no_such_type_never_falls_back_to_all_types(self):
        for types in [[], ['unknown'], ['EXPLICIT_CROSSWALK'], ['ship_to_in_sales_area:2000:10:00']]:
            with self.subTest(types=types):
                self.assertEqual(shortest_path(self.model, A, C, relation_types=types), [])

    def test_self_path_has_zero_edges_but_missing_node_has_none(self):
        self.assertEqual(shortest_path(self.model, A, A, relation_types=[]), [A])
        self.assertEqual(shortest_path(self.model, 'missing', 'missing', relation_types=[]), [])

    def test_bad_filter_types_are_rejected_without_silent_normalization(self):
        for types in ['explicit_crosswalk', b'abc', 3, True, {}, {'x': 1}, [None], [''], [' '], [' explicit_crosswalk'], ['explicit_crosswalk ']]:
            with self.subTest(types=types), self.assertRaises(ValueError):
                shortest_path(self.model, A, B, relation_types=types)

    def test_collection_duplicates_and_sets_have_same_meaning(self):
        for types in [[CROSSWALK, CROSSWALK], (CROSSWALK,), {CROSSWALK}, frozenset([CROSSWALK])]:
            self.assertEqual(shortest_path(self.model, A, B, relation_types=types), [A, B])

    def test_implicit_related_to_type_is_selectable(self):
        model = {'nodes': [{'id': 'a'}, {'id': 'b'}], 'relationships': [{'from': 'a', 'to': 'b'}]}
        self.assertEqual(shortest_path(model, 'a', 'b', relation_types=['related_to']), ['a', 'b'])

    def test_broken_edge_is_not_a_shortcut_and_cycles_terminate(self):
        model = {'nodes': [{'id': n} for n in ['a', 'b', 'c']], 'relationships': [
            {'from': 'a', 'to': 'absent', 'type': 'x'}, {'from': 'absent', 'to': 'c', 'type': 'x'},
            {'from': 'a', 'to': 'b', 'type': 'x'}, {'from': 'b', 'to': 'a', 'type': 'x'}]}
        self.assertEqual(shortest_path(model, 'a', 'c', relation_types=['x']), [])

    def test_filter_does_not_mutate_source_or_provenance(self):
        saved = copy.deepcopy(self.model)
        shortest_path(self.model, A, B, relation_types=[CROSSWALK])
        self.assertEqual(self.model, saved)
        self.assertEqual(self.model['relationships'][0]['provenance'], {'file': 'crosswalk.csv', 'row': 2})

    def test_fixture_distinguishes_policy_from_partner_assignment(self):
        self.assertTrue(analyze(self.model)['valid'])
        policy = json.loads((EXAMPLE / 'policy.json').read_text())
        self.assertTrue(evaluate(self.model, policy)['passed'])
        partners = [r for r in self.model['relationships'] if r['type'] == PARTNER]
        self.assertEqual([r['to'] for r in partners], [C, D])
        self.assertEqual([r['provenance']['row'] for r in partners], [2, 3])
        policy['relationship_rules'][PARTNER] = {'max_outgoing': 1}
        self.assertFalse(evaluate(self.model, policy)['passed'])
        self.assertEqual(shortest_path(self.model, B, C, relation_types=[PARTNER]), [B, C])

    def test_unified_cli_repeat_filter_and_exit_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'model.json'; p.write_text(json.dumps(self.model))
            cases = [([], 0, f'{A} -> {B} -> {C}\n'),
                     (['--relation', CROSSWALK], 2, 'NO_PATH\n'),
                     (['--relation', CROSSWALK, '--relation', PARTNER], 0, f'{A} -> {B} -> {C}\n')]
            for flags, code, expected in cases:
                out = io.StringIO()
                with redirect_stdout(out):
                    actual = main(['path', str(p), A, C, *flags])
                self.assertEqual(actual, code); self.assertEqual(out.getvalue(), expected)

    def test_cli_rejects_blank_filter_with_fixed_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'model.json'; p.write_text(json.dumps(self.model))
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as caught:
                main(['path', str(p), A, B, '--relation', ' '])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(out.getvalue(), '')
            self.assertIn('relation types must be non-blank exact names', err.getvalue())


if __name__ == '__main__':
    unittest.main()
