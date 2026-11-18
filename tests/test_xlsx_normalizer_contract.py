import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from xlsx_adapter import _normalizers, build_model, normalize_row

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('contract_writer', ROOT / 'examples/xlsx/make_sample.py')
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


class XlsxNormalizerContractTests(unittest.TestCase):
    def source(self, **updates):
        return dict(file='data.xlsx', sheet='Data', id='OBJ:{ID}', **updates)

    def test_collection_must_be_mapping_even_without_sources(self):
        for bad in (None, False, 0, '', [], ['upper']):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build_model({'normalizers': bad}, Path('/not-opened'))

    def test_source_collection_must_be_mapping(self):
        for bad in (None, False, 0, '', []):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _normalizers({}, {'normalizers': bad})

    def test_rule_values_are_not_coerced(self):
        for bad in (None, False, 1, {'upper': False}, ('upper',), {'upper'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _normalizers({}, {'normalizers': {'ID': bad}})

    def test_each_rule_is_a_known_exact_string(self):
        for bad in ([None], [False], [1], [{}], [['upper']], 'UPPER', ' upper', '', 'typo'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _normalizers({}, {'normalizers': {'ID': bad}})

    def test_column_names_are_nonblank_strings(self):
        for field in ('', '  ', 1, None):
            with self.subTest(field=field), self.assertRaises(ValueError):
                _normalizers({}, {'normalizers': {field: 'upper'}})

    def test_rules_compose_in_order_without_mutation_or_override(self):
        manifest={'normalizers': {'ID': ['strip', 'lower']}}
        source={'normalizers': {'ID': ['upper'], 'OTHER': []}}
        old=copy.deepcopy((manifest, source));rules=_normalizers(manifest,source)
        self.assertEqual(rules, {'ID': ['strip', 'lower', 'upper'], 'OTHER': []})
        self.assertEqual(normalize_row({'ID':' Ab ','OTHER':'x'},rules)[0]['ID'],'AB')
        self.assertEqual((manifest,source),old)
        self.assertEqual(_normalizers(manifest,{'normalizers':{'ID':[]}})['ID'],['strip','lower'])

    def test_valid_empty_configuration_remains_noop(self):
        self.assertEqual(_normalizers({},{}),{})
        self.assertEqual(_normalizers({'normalizers':{}},{'normalizers':{}}),{})
        self.assertEqual(build_model({'node_sources':[]},Path('/not-opened')),{'nodes':[],'relationships':[]})

    def test_later_invalid_source_fails_before_any_workbook_read(self):
        manifest={'node_sources':[self.source(),self.source(normalizers={'ID':{'upper':False}})]}
        report={}
        with patch('xlsx_adapter.read_sheet',side_effect=AssertionError('must not read')):
            with self.assertRaises(ValueError):build_model(manifest,Path('/not-opened'),import_report=report)
        self.assertFalse(report['complete']);self.assertFalse(report['model_returned'])
        self.assertTrue(all(s['status']=='not_started' for s in report['sources']))

    def build(self, rows, spec, global_rules=None):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);writer.build(base/'data.xlsx',rows=rows,sheet_name='Data')
            manifest=spec
            if global_rules is not None:manifest['normalizers']=global_rules
            return build_model(manifest,base)

    def test_unknown_rule_rejected_for_header_only_export(self):
        with self.assertRaises(ValueError):
            self.build([['ID']],{'node_sources':[self.source(normalizers={'ID':'typo'})]})

    def test_missing_node_column_rejected_for_header_only_export(self):
        with self.assertRaisesRegex(ValueError,'missing column'):
            self.build([['ID']],{'node_sources':[self.source(normalizers={'MISSING':'upper'})]})

    def test_missing_relationship_column_rejected_for_header_only_export(self):
        source={'file':'data.xlsx','sheet':'Data','from':'A:{ID}','to':'B:{ID}','normalizers':{'MISSING':'upper'}}
        with self.assertRaisesRegex(ValueError,'missing column'):
            self.build([['ID']],{'relationship_sources':[source]})

    def test_missing_global_column_rejected_on_header(self):
        with self.assertRaisesRegex(ValueError,'missing column'):
            self.build([['ID']],{'node_sources':[self.source()]},{'MISSING':'upper'})

    def test_empty_sheet_with_declared_columns_rejected(self):
        with self.assertRaisesRegex(ValueError,'without a header'):
            self.build([],{'node_sources':[self.source(normalizers={'ID':'upper'})]})

    def test_empty_sheet_without_normalizers_keeps_legacy_behavior(self):
        self.assertEqual(self.build([],{'node_sources':[self.source()]}),{'nodes':[],'relationships':[]})

    def test_header_only_valid_normalizers_keep_empty_model(self):
        for rules in ({'ID':'upper'},{'ID':['strip','strip_leading_zeros']},{'ID':[]}):
            with self.subTest(rules=rules):
                self.assertEqual(self.build([['ID']],{'node_sources':[self.source(normalizers=rules)]}),{'nodes':[],'relationships':[]})

    def test_all_operations_retain_explicit_semantics(self):
        row,changes=normalize_row({'ID':' 000ab '},_normalizers({'normalizers':{'ID':'strip'}},{'normalizers':{'ID':['upper','lower','strip_leading_zeros']}}))
        self.assertEqual(row,{'ID':'ab'});self.assertEqual(changes,{'ID':{'from':' 000ab ','to':'ab'}})

    def test_collision_provenance_remains_not_identity_approval(self):
        model=self.build([['ID'],['0004711'],['4711']],{'node_sources':[self.source(normalizers={'ID':'strip_leading_zeros'})]})
        self.assertEqual(len(model['nodes']),1)
        self.assertEqual(model['nodes'][0]['identity_collisions'],['OBJ:0004711','OBJ:4711'])
        self.assertEqual(model['nodes'][0]['provenance'][0]['raw_identity'],'OBJ:0004711')

    def test_both_source_entrypoints_abort_without_graph_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);writer.build(base/'data.xlsx',rows=[['ID']],sheet_name='Data')
            manifest=base/'manifest.json';manifest.write_text(json.dumps({'node_sources':[self.source(normalizers={'ID':{'upper':False}})]}))
            output=base/'graph.json';output.write_text('previous graph')
            for entry in ('unified','module'):
                report=base/(entry+'.json')
                code=f"import sys;sys.path.insert(0,{str(ROOT)!r});from "+('drm_cli' if entry=='unified' else 'xlsx_adapter')+" import main;raise SystemExit(main())"
                args=[sys.executable,'-c',code]+(['import-xlsx'] if entry=='unified' else [])+[str(manifest),'--output',str(output),'--import-report',str(report)]
                r=subprocess.run(args,capture_output=True,text=True)
                self.assertEqual(r.returncode,2,r.stderr);self.assertNotIn('Traceback',r.stderr)
                self.assertEqual(output.read_text(),'previous graph')
                ledger=json.loads(report.read_text());self.assertFalse(ledger['complete']);self.assertFalse(ledger['model_returned'])


if __name__=='__main__':unittest.main()
