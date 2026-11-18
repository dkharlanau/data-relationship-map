import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import csv_adapter
import xlsx_adapter
from relationship_artifacts import build_index
from relationship_handoff import build_handoff, verify_handoff
from relationship_investigation import MetadataConflictError, build_investigation, render_html, render_markdown
from test_xlsx_adapter import write_minimal_xlsx

ROOT = Path(__file__).resolve().parents[1]


def base_model():
    return {'nodes':[{'id':'A','label':'First','provenance':[{'file':'objects.csv','row':2},{'file':'objects.csv','row':4}]},
                     {'id':'B'}], 'relationships':[{'from':'A','to':'B','type':'mapped_to'}]}


class MetadataConflictReviewTests(unittest.TestCase):
    def test_csv_import_conflict_is_visible_without_selecting_winner(self):
        manifest,base=csv_adapter.load_manifest(ROOT/'examples/bp-metadata-conflict/manifest.json')
        model=csv_adapter.build_model(manifest,base);before=copy.deepcopy(model)
        policy={'relationship_rules':{'explicit_crosswalk':{'max_outgoing':1,'max_incoming':1}}}
        report=build_investigation(model,policy=policy,focus='LEGACY:100:0004711')
        self.assertEqual(report['status'],'findings');self.assertTrue(report['structural']['valid'])
        self.assertTrue(report['policy']['passed']);self.assertEqual(report['summary']['policy_finding_count'],0)
        self.assertEqual(report['summary']['structural_finding_count'],0)
        self.assertEqual(report['summary']['metadata_conflict_count'],1)
        conflict=report['metadata_conflicts'][0]
        self.assertEqual(conflict['values'],['North account','South account'])
        self.assertEqual([x['row'] for x in conflict['contributing_node_provenance']],[2,4])
        self.assertEqual(model,before);self.assertEqual(model['nodes'][0]['label'],'North account')
        self.assertIn('not value-to-row attribution',render_markdown(report))
        self.assertIn('not an endorsed winner',render_markdown(report))

    def test_xlsx_conflict_preserves_sheet_and_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);write_minimal_xlsx(base/'objects.xlsx',[['ID','LABEL'],['0001','North'],['0001','South']],sheet_name='Partners')
            manifest={'node_sources':[{'file':'objects.xlsx','sheet':'Partners','id':'{ID}','label':'{LABEL}'}]}
            model=xlsx_adapter.build_model(manifest,base)
            report=build_investigation(model,focus='0001');conflict=report['metadata_conflicts'][0]
            self.assertEqual(conflict['node'],'0001')
            self.assertEqual(conflict['values'],['North','South'])
            self.assertEqual([p['row'] for p in conflict['contributing_node_provenance']],[2,3])
            self.assertTrue(all(p['sheet']=='Partners' for p in conflict['contributing_node_provenance']))

    def test_count_is_node_field_not_values_or_provenance(self):
        model=base_model();model['nodes'][0]['conflicts']={'system':['S2','S1'],'label':['C','B','A','A']}
        r=build_investigation(model)
        self.assertEqual(r['summary']['metadata_conflict_count'],2)
        self.assertEqual([x['field'] for x in r['metadata_conflicts']],['label','system'])
        self.assertEqual(r['metadata_conflicts'][0]['values'],['A','B','C'])
        self.assertEqual(r,build_investigation(model))

    def test_empty_or_absent_conflict_keeps_report_shape(self):
        model=base_model();plain=build_investigation(model)
        self.assertNotIn('metadata_conflicts',plain);self.assertNotIn('metadata_conflict_count',plain['summary'])
        self.assertNotIn('Recorded metadata conflicts',render_markdown(plain))
        # Without focus, empty conflicts do not alter report contents.
        model['nodes'][0]['conflicts']={}
        self.assertEqual(plain,build_investigation(model))

    def test_conflict_values_are_inert_markdown_and_html(self):
        model=base_model();model['nodes'][0]['conflicts']={'label':['<script>alert(1)</script>','`link`\n[click](https://example.invalid)']}
        report=build_investigation(model);md=render_markdown(report);html=render_html(report)
        self.assertIn('`` [',md)  # fence longer than the supplied inline backtick
        self.assertIn('\\n[click]',md);self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)

    def test_bad_conflict_shape_fails_without_echo(self):
        invalid=[None,[],True,{'private_field':['A','B']},{'label':'PRIVATE'},{'label':['A']},
                 {'label':['A','A']},{'label':['A',None]},{'label':['A','']},{'label':['A',' ']},{'label':[{},'B']}]
        for value in invalid:
            with self.subTest(value=value):
                model=base_model();model['nodes'][0]['conflicts']=value
                with self.assertRaises(MetadataConflictError) as caught:build_investigation(model)
                self.assertNotIn('PRIVATE',str(caught.exception));self.assertNotIn('private_field',str(caught.exception))

    def test_status_precedence_stays_invalid_focus_or_model(self):
        model=base_model();model['nodes'][0]['conflicts']={'label':['First','Second']}
        self.assertEqual(build_investigation(model,focus='MISSING')['status'],'invalid_focus')
        model['relationships'][0]['to']='MISSING'
        self.assertEqual(build_investigation(model)['status'],'invalid_model')

    def test_unknown_provenance_is_explicit_not_invented(self):
        model=base_model();model['nodes'][0].pop('provenance');model['nodes'][0]['conflicts']={'label':['First','Second']}
        report=build_investigation(model)
        self.assertEqual(report['metadata_conflicts'][0]['contributing_node_provenance'],[])
        self.assertIn('not supplied',render_markdown(report))

    def test_conflict_handoff_is_verified_findings_not_automatic_peg_defect(self):
        model=base_model();model['nodes'][0]['conflicts']={'label':['First','Second']}
        with tempfile.TemporaryDirectory() as tmp:
            manifest=build_handoff(model,tmp,focus='A',policy={})
            self.assertEqual(manifest['status'],'findings');self.assertEqual(manifest['summary']['metadata_conflicts'],1)
            self.assertTrue(verify_handoff(tmp)['valid'])
            report=json.loads((Path(tmp)/'investigation.json').read_text())
            self.assertEqual(report['metadata_conflicts'][0]['node'],'A')
            index=json.loads((Path(tmp)/'artifact-index.json').read_text())
            self.assertTrue(index['valid']);self.assertTrue(index['policy_passed']);self.assertEqual(index['findings'],[])
            self.assertEqual(index['objects'][0]['conflicts'],{'label':['First','Second']})

    def test_bounded_handoff_excludes_unrelated_conflict(self):
        model=base_model();model['nodes'].append({'id':'C','conflicts':{'label':['Elsewhere','Other']}})
        self.assertEqual(build_investigation(model,focus='A')['summary']['metadata_conflict_count'],1)
        with tempfile.TemporaryDirectory() as tmp:
            manifest=build_handoff(model,tmp,focus='A')
            self.assertEqual(manifest['status'],'clear');self.assertNotIn('metadata_conflicts',manifest['summary'])
            report=json.loads((Path(tmp)/'investigation.json').read_text())
            self.assertNotIn('metadata_conflicts',report);self.assertNotIn('Elsewhere',json.dumps(report))

    def test_malformed_unrelated_conflict_stops_before_pack_write(self):
        model=base_model();model['nodes'].append({'id':'C','conflicts':[]})
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)/'pack'
            with self.assertRaises(MetadataConflictError):build_handoff(model,destination,focus='A')
            self.assertFalse(destination.exists())

    def test_invalid_cli_conflict_does_not_overwrite_retained_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);model=base_model();model['nodes'][0]['conflicts']={'label':'PRIVATE'}
            source=base/'model.json';source.write_text(json.dumps(model))
            out=base/'report.json';out.write_text('retained');pack=base/'pack';pack.mkdir();(pack/'manifest.json').write_text('retained')
            for command,args in [('investigate',[source,'--json-output',out]),('handoff',['build',source,pack,'--focus','A'])]:
                for prefix in ([sys.executable,'-B',ROOT/'drm_cli.py',command], [sys.executable,'-B',ROOT/('relationship_investigation.py' if command=='investigate' else 'relationship_handoff.py')]):
                    result=subprocess.run([*map(str,prefix),*map(str,args)],capture_output=True,text=True)
                    self.assertEqual(result.returncode,2,result.stderr);self.assertEqual(result.stdout,'')
                    self.assertNotIn('Traceback',result.stderr);self.assertNotIn('PRIVATE',result.stderr)
                    self.assertEqual(out.read_text(),'retained');self.assertEqual((pack/'manifest.json').read_text(),'retained')
                    self.assertEqual([p.name for p in pack.iterdir()],['manifest.json'])


if __name__=='__main__':unittest.main()
