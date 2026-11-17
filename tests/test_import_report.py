"""Source accounting is optional, deterministic and explicit about abort scope."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import csv_adapter
import xlsx_adapter
from test_xlsx_adapter import write_minimal_xlsx

ROOT = Path(__file__).resolve().parents[1]


class ImportReportTests(unittest.TestCase):
    def source(self, base, kind, rows):
        name = 'source.' + kind
        if kind == 'csv':
            with (base / name).open('w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(rows)
        else:
            write_minimal_xlsx(base / name, rows, sheet_name='Data')
        return {'file': name, **({'sheet': 'Data'} if kind == 'xlsx' else {})}

    def assert_reconciled(self, report):
        for value in [report, *report['sources']]:
            count = value['counts']
            self.assertEqual(count['encountered'], sum(count[k] for k in ('accepted', 'skipped', 'rejected')))
        for key in report['counts']:
            self.assertEqual(report['counts'][key], sum(s['counts'][key] for s in report['sources']))

    def test_complete_accounts_blank_merged_and_multiline_rows_without_changing_model(self):
        rows = [['ID', 'LABEL'], ['001', 'line1\nline2'], [], [' ', ''], ['001', 'Other'], ['0', 'Zero']]
        for kind, adapter in [('csv', csv_adapter), ('xlsx', xlsx_adapter)]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp); source = self.source(base, kind, rows)
                manifest = {'node_sources': [{**source, 'id': '{ID}', 'label': '{LABEL}'}]}
                expected = adapter.build_model(manifest, base)
                report = {'obsolete': True}
                actual = adapter.build_model(manifest, base, import_report=report)
                self.assertEqual(actual, expected)
                self.assertEqual([n['id'] for n in actual['nodes']], ['001', '0'])
                self.assertNotIn('obsolete', report)
                self.assertTrue(report['complete']); self.assertTrue(report['model_returned'])
                self.assertEqual(report['counts'], dict(encountered=5, accepted=3, skipped=2, rejected=0))
                records = report['sources'][0]['records']
                self.assertEqual([r['reason'] for r in records], ['node_created', 'blank_record', 'blank_record', 'node_merged', 'node_created'])
                self.assertEqual(records[0]['row'], 2)
                self.assertEqual(records[0]['row_end'], 3 if kind == 'csv' else 2)
                self.assertEqual(records[-1]['row'], 7 if kind == 'csv' else 6)
                self.assertNotIn('line1', json.dumps(report))
                second = {}; adapter.build_model(manifest, base, import_report=second)
                self.assertEqual(report, second)
                self.assert_reconciled(report)

    def test_repeated_declarations_count_separately_and_duplicate_edges_keep_references(self):
        for kind, adapter in [('csv', csv_adapter), ('xlsx', xlsx_adapter)]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp); source = self.source(base, kind, [['FROM', 'TO'], ['0001', '0002'], ['0001', '0002'], ['0001', '0003']])
                manifest = {'node_sources': [{**source, 'id': 'A:{FROM}'}, {**source, 'id': 'B:{TO}'}],
                            'relationship_sources': [{**source, 'from': 'A:{FROM}', 'to': 'B:{TO}', 'type': 'sold_to_ship_to'}]}
                report = {}; model = adapter.build_model(manifest, base, import_report=report)
                self.assertEqual(report['counts']['encountered'], 9)
                self.assertEqual(len(model['nodes']), 3); self.assertEqual(len(model['relationships']), 3)
                refs = [r['outputs'][0] for r in report['sources'][2]['records']]
                self.assertEqual([r['index'] for r in refs], [0, 1, 2])
                self.assertEqual([r['type'] for r in refs], ['sold_to_ship_to'] * 3)
                self.assert_reconciled(report)

    def test_abort_keeps_remaining_sources_unvisited_and_no_model(self):
        for kind, adapter in [('csv', csv_adapter), ('xlsx', xlsx_adapter)]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp); source = self.source(base, kind, [['ID', 'LABEL'], ['001', 'Good'], ['', 'Bad'], ['003', 'Not visited']])
                manifest = {'node_sources': [{**source, 'id': '{ID}'}, {**source, 'id': 'copy:{ID}'}]}
                report = {}
                with self.assertRaises(ValueError): adapter.build_model(manifest, base, import_report=report)
                self.assertFalse(report['complete']); self.assertFalse(report['model_returned'])
                self.assertEqual(report['counts'], dict(encountered=2, accepted=1, skipped=0, rejected=1))
                self.assertEqual([s['status'] for s in report['sources']], ['aborted', 'not_started'])
                self.assertEqual(report['sources'][0]['records'][-1]['reason'], 'blank_node_id')
                self.assertEqual(report['sources'][0]['records'][-1]['outputs'], [])
                self.assert_reconciled(report)

    def test_relationship_component_and_template_rejections_have_reason_codes(self):
        cases = [({'from': '{FROM}', 'to': '{TO}'}, 'blank_relationship_endpoint'),
                 ({'from': 'S4:{FROM}', 'to': 'S4:{TO}', 'required_identity_columns': ['TO']}, 'blank_identity_component'),
                 ({'from': '{UNKNOWN}', 'to': '{TO}'}, 'missing_template_column')]
        for kind, adapter in [('csv', csv_adapter), ('xlsx', xlsx_adapter)]:
            for config, reason in cases:
                with self.subTest(kind=kind, reason=reason), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp); source = self.source(base, kind, [['FROM', 'TO'], ['001', '']])
                    report = {}
                    with self.assertRaises(ValueError): adapter.build_model({'relationship_sources': [{**source, **config}]}, base, import_report=report)
                    self.assertEqual(report['sources'][0]['records'][0]['reason'], reason)
                    self.assert_reconciled(report)

    def test_header_failure_is_source_error_not_a_fabricated_data_row(self):
        for kind, adapter in [('csv', csv_adapter), ('xlsx', xlsx_adapter)]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp); source = self.source(base, kind, [['ID', 'ID'], ['1', '2']]); report = {}
                with self.assertRaises(ValueError): adapter.build_model({'node_sources': [{**source, 'id': '{ID}'}]}, base, import_report=report)
                self.assertEqual(report['counts']['encountered'], 0)
                self.assertEqual(report['sources'][0]['error'], 'source_or_contract_error')
                self.assertFalse(report['complete']); self.assert_reconciled(report)

    def test_csv_parser_failures_keep_physical_location_and_abort(self):
        for text in ['ID,LABEL\n1,good\n2,too,wide\n', 'ID,LABEL\n1,good\n2,"unterminated\nmore\n']:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp); (base/'source.csv').write_text(text); report = {}
                with self.assertRaises(ValueError): csv_adapter.build_model({'node_sources': [{'file':'source.csv','id':'{ID}'}]}, base, import_report=report)
                last = report['sources'][0]['records'][-1]
                self.assertEqual(last['row'], 3); self.assertEqual(last['disposition'], 'rejected')
                self.assert_reconciled(report)

    def test_cli_preserves_old_graph_but_retains_partial_report(self):
        for kind in ['csv', 'xlsx']:
            for entry in [[sys.executable, '-B', str(ROOT/'drm_cli.py'), 'import-'+kind], [sys.executable, '-B', str(ROOT/(kind+'_adapter.py'))]]:
                with self.subTest(kind=kind, entry=entry), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp); source = self.source(base, kind, [['ID', 'LABEL'], ['1', 'Valid'], ['', 'Missing']])
                    manifest = base/'manifest.json'; manifest.write_text(json.dumps({'node_sources': [{**source,'id':'{ID}'}]}))
                    graph = base/'graph.json'; graph.write_text('old graph'); ledger = base/'report.json'
                    result = subprocess.run([*entry, str(manifest), '--output', str(graph), '--import-report', str(ledger)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stderr); self.assertEqual(result.stdout, '')
                    self.assertNotIn('Traceback',result.stderr); self.assertEqual(graph.read_text(), 'old graph')
                    report = json.loads(ledger.read_text()); self.assertFalse(report['complete']); self.assert_reconciled(report)

    def test_cli_rejects_output_aliases_including_hardlinks_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); source = self.source(base, 'csv', [['ID'],['1']]); manifest=base/'manifest.json'
            manifest.write_text(json.dumps({'node_sources':[{**source,'id':'{ID}'}]}))
            raw=base/source['file']; hard=base/'hard'; os.link(raw,hard); sym=base/'sym'; sym.symlink_to(raw)
            cases = [(base/'graph', raw), (base/'graph', hard), (base/'graph', sym), (base/'same',base/'same'),(raw,base/'report'),(manifest,base/'report')]
            before={p:p.read_bytes() for p in (raw,manifest)}
            for graph,report in cases:
                with self.subTest(graph=graph,report=report):
                    run=subprocess.run([sys.executable,'-B',str(ROOT/'drm_cli.py'),'import-csv',str(manifest),'--output',str(graph),'--import-report',str(report)],capture_output=True,text=True)
                    self.assertEqual(run.returncode,2,run.stderr)
                    for p,data in before.items(): self.assertEqual(p.read_bytes(),data)

    def test_report_write_failure_does_not_replace_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=self.source(base,'csv',[['ID'],['1']]); manifest=base/'manifest.json'
            manifest.write_text(json.dumps({'node_sources':[{**source,'id':'{ID}'}]})); graph=base/'graph';graph.write_text('retained')
            run=subprocess.run([sys.executable,'-B',str(ROOT/'drm_cli.py'),'import-csv',str(manifest),'--output',str(graph),'--import-report',str(base/'missing'/'report')],capture_output=True,text=True)
            self.assertEqual(run.returncode,2);self.assertEqual(graph.read_text(),'retained');self.assertNotIn('Traceback',run.stderr)

    def test_xlsx_implicit_gaps_are_not_invented_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=self.source(base,'xlsx',[['ID'],['001']]); path=base/source['file']
            with zipfile.ZipFile(path) as z: entries={n:z.read(n) for n in z.namelist()}
            entries['xl/worksheets/sheet1.xml']=entries['xl/worksheets/sheet1.xml'].replace(b'r="2"',b'r="10"').replace(b'A2',b'A10')
            with zipfile.ZipFile(path,'w') as z:
                for n,b in entries.items():z.writestr(n,b)
            report={};xlsx_adapter.build_model({'node_sources':[{**source,'id':'{ID}'}]},base,import_report=report)
            self.assertEqual(report['counts']['encountered'],1);self.assertEqual(report['sources'][0]['records'][0]['row'],10)

    def test_bad_xlsx_archive_or_xml_aborts_cleanly(self):
        for corrupt in ('zip', 'xml'):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp); source = self.source(base, 'xlsx', [['ID'],['1']]); path=base/source['file']
                if corrupt == 'zip': path.write_text('not a zip')
                else:
                    with zipfile.ZipFile(path) as z: entries={n:z.read(n) for n in z.namelist()}
                    entries['xl/worksheets/sheet1.xml']=b'<unterminated'
                    with zipfile.ZipFile(path,'w') as z:
                        for n,b in entries.items(): z.writestr(n,b)
                manifest={'node_sources':[{**source,'id':'{ID}'}]};report={}
                with self.assertRaises(Exception): xlsx_adapter.build_model(manifest,base,import_report=report)
                self.assertEqual(report['status'],'aborted');self.assert_reconciled(report)
                (base/'manifest.json').write_text(json.dumps(manifest))
                result=subprocess.run([sys.executable,'-B',str(ROOT/'drm_cli.py'),'import-xlsx',str(base/'manifest.json'),'--import-report',str(base/'report.json')],capture_output=True,text=True)
                self.assertEqual(result.returncode,2,result.stderr);self.assertNotIn('Traceback',result.stderr)
                self.assertEqual(json.loads((base/'report.json').read_text())['status'],'aborted')

    def test_invalid_template_access_is_accounted_as_rejection(self):
        for kind,adapter in [('csv',csv_adapter),('xlsx',xlsx_adapter)]:
            for template in ('{ID[9]}','{ID.no_such_attr}'):
                with self.subTest(kind=kind,template=template),tempfile.TemporaryDirectory() as tmp:
                    base=Path(tmp);source=self.source(base,kind,[['ID'],['x']]);report={}
                    with self.assertRaises((IndexError,AttributeError)):
                        adapter.build_model({'node_sources':[{**source,'id':template}]},base,import_report=report)
                    self.assertEqual(report['status'],'aborted');self.assertEqual(report['counts']['rejected'],1);self.assert_reconciled(report)

    def test_graph_delivery_failure_is_clean_and_not_import_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=self.source(base,'csv',[['ID'],['1']]);manifest=base/'manifest.json'
            manifest.write_text(json.dumps({'node_sources':[{**source,'id':'{ID}'}]}));graph=base/'graph';graph.mkdir()
            (graph/'retained').write_text('keep');ledger=base/'report.json'
            result=subprocess.run([sys.executable,'-B',str(ROOT/'drm_cli.py'),'import-csv',str(manifest),'--output',str(graph),'--import-report',str(ledger)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2);self.assertNotIn('Traceback',result.stderr)
            self.assertEqual((graph/'retained').read_text(),'keep')
            report=json.loads(ledger.read_text());self.assertTrue(report['model_returned'])
            self.assertEqual(list(base.glob('.drm-report-*')),[])

    def test_invalid_source_contract_never_leaves_in_progress_report(self):
        for adapter in (csv_adapter,xlsx_adapter):
            for manifest in ({'node_sources':None},{'node_sources':[{}]},{'node_sources':[1]}):
                with self.subTest(adapter=adapter.__name__,manifest=manifest):
                    report={}
                    with self.assertRaises((TypeError,KeyError)):
                        adapter.build_model(manifest,Path('.'),import_report=report)
                    self.assertEqual(report['status'],'aborted')
                    self.assertEqual(report['error'],'manifest_contract_error');self.assert_reconciled(report)

    def test_empty_and_header_only_sources_report_zero_not_missing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            for kind,adapter in [('csv',csv_adapter),('xlsx',xlsx_adapter)]:
                source=self.source(base,kind,[['ID']]);report={}
                self.assertEqual(adapter.build_model({'node_sources':[{**source,'id':'{ID}'}]},base,import_report=report),{'nodes':[],'relationships':[]})
                self.assertTrue(report['complete']);self.assertEqual(report['counts']['encountered'],0)
                self.assert_reconciled(report)


if __name__=='__main__': unittest.main()
