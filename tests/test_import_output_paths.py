import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from import_report import validate_output_paths

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alias_writer',ROOT/'examples/xlsx/make_sample.py')
writer=importlib.util.module_from_spec(spec);spec.loader.exec_module(writer)


class ImportOutputPathsTests(unittest.TestCase):
    def fixture(self, base, fmt):
        source=base/('data.'+fmt)
        if fmt=='csv':source.write_text('ID,TO\n0004711,0009001\n0009001,0004711\n')
        else:writer.build(source,rows=[['ID','TO'],['0004711','0009001'],['0009001','0004711']],sheet_name='Data')
        manifest={'node_sources':[{'file':source.name,'sheet':'Data','id':'{ID}'}],
                  'relationship_sources':[{'file':source.name,'sheet':'Data','from':'{ID}','to':'{TO}'}]}
        path=base/'manifest.json';path.write_text(json.dumps(manifest));return source,path,manifest

    def command(self, fmt, entry, manifest, output=None, report=None):
        module='drm_cli' if entry=='unified' else fmt+'_adapter'
        code=f"import sys;sys.path.insert(0,{str(ROOT)!r});from {module} import main;raise SystemExit(main())"
        args=[sys.executable,'-c',code]+(['import-'+fmt] if entry=='unified' else [])+[str(manifest)]
        if output is not None:args+=['--output',str(output)]
        if report is not None:args+=['--import-report',str(report)]
        return subprocess.run(args,capture_output=True,text=True)

    def test_graph_only_direct_guard_includes_manifest_and_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv')
            for output in (source,path):
                with self.subTest(output=output),self.assertRaisesRegex(ValueError,'must not overwrite'):
                    validate_output_paths(path,manifest,base,str(output))

    def test_report_only_still_checks_source_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv')
            with self.assertRaises(ValueError):validate_output_paths(path,manifest,base,None,str(source))

    def test_no_output_does_not_inspect_source_paths(self):
        validate_output_paths(Path('unused'),{'node_sources':[None]},Path('unused'),None)

    def test_valid_distinct_paths_remain_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv')
            validate_output_paths(path,manifest,base,str(base/'graph.json'))
            validate_output_paths(path,manifest,base,str(base/'graph.json'),str(base/'report.json'))

    def test_report_and_graph_alias_remains_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv')
            with self.assertRaises(ValueError):validate_output_paths(path,manifest,base,str(base/'same'),str(base/'same'))

    def test_graph_only_hardlinks_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv')
            for kind in ('hard','symbolic'):
                alias=base/kind
                if kind=='hard':os.link(source,alias)
                else:alias.symlink_to(source)
                with self.subTest(kind=kind),self.assertRaises(ValueError):validate_output_paths(path,manifest,base,str(alias))

    def test_relative_parent_directory_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv');(base/'sub').mkdir()
            with self.assertRaises(ValueError):validate_output_paths(path,manifest,base,str(base/'sub/../data.csv'))

    def test_symlinked_parent_directory_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv');alias=base/'linked';alias.symlink_to(base,target_is_directory=True)
            with self.assertRaises(ValueError):validate_output_paths(path,manifest,base,str(alias/'data.csv'))

    def test_relationship_only_source_is_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv');manifest.pop('node_sources')
            with self.assertRaises(ValueError):validate_output_paths(path,manifest,base,str(source))

    def test_both_formats_and_entrypoints_reject_graph_only_source_alias(self):
        for fmt in ('csv','xlsx'):
            for entry in ('unified','module'):
                with self.subTest(fmt=fmt,entry=entry),tempfile.TemporaryDirectory() as tmp:
                    base=Path(tmp);source,path,manifest=self.fixture(base,fmt);before={p:p.read_bytes() for p in (source,path)}
                    r=self.command(fmt,entry,path,source);self.assertEqual(r.returncode,2,r.stderr)
                    self.assertEqual(r.stdout,'');self.assertNotIn('Traceback',r.stderr)
                    self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_output_refusal_precedes_source_parse_and_preserves_sidecar(self):
        for fmt in ('csv','xlsx'):
            with self.subTest(fmt=fmt),tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);source,path,manifest=self.fixture(base,fmt);source.write_bytes(b'not a valid table or workbook')
                sidecar=base/'report.json';sidecar.write_text('old ledger')
                r=self.command(fmt,'unified',path,source,sidecar)
                self.assertEqual(r.returncode,2);self.assertIn('must not overwrite',r.stderr)
                self.assertEqual(source.read_bytes(),b'not a valid table or workbook');self.assertEqual(sidecar.read_text(),'old ledger')

    def test_alias_refusal_does_not_create_new_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv');report=base/'new.json'
            r=self.command('csv','unified',path,path,report);self.assertEqual(r.returncode,2);self.assertFalse(report.exists())

    def test_stdout_and_unrelated_output_keep_same_model(self):
        for fmt in ('csv','xlsx'):
            with self.subTest(fmt=fmt),tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);source,path,manifest=self.fixture(base,fmt);before={p:p.read_bytes() for p in (source,path)}
                stdout=self.command(fmt,'unified',path);self.assertEqual(stdout.returncode,0,stdout.stderr)
                out=base/'graph.json';out.write_text('previous unrelated output')
                written=self.command(fmt,'unified',path,out);self.assertEqual(written.returncode,0,written.stderr)
                self.assertEqual(json.loads(stdout.stdout),json.loads(out.read_text()))
                self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_output_symlink_loop_is_a_clean_cli_error(self):
        for fmt in ('csv', 'xlsx'):
            for entry in ('unified', 'module'):
                with self.subTest(fmt=fmt, entry=entry), tempfile.TemporaryDirectory() as tmp:
                    base=Path(tmp);source,path,manifest=self.fixture(base,fmt)
                    loop=base/'loop';loop.symlink_to('loop')
                    before={p:p.read_bytes() for p in (source,path)}
                    r=self.command(fmt,entry,path,loop)
                    self.assertEqual(r.returncode,2,r.stderr)
                    self.assertEqual(r.stdout,'');self.assertNotIn('Traceback',r.stderr)
                    self.assertTrue(loop.is_symlink())
                    self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_source_symlink_loop_preserves_existing_graph_and_report(self):
        for fmt in ('csv', 'xlsx'):
            with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);source,path,manifest=self.fixture(base,fmt)
                source.unlink();source.symlink_to(source.name)
                out=base/'graph.json';out.write_text('old graph')
                report=base/'report.json';report.write_text('old report')
                r=self.command(fmt,'unified',path,out,report)
                self.assertEqual(r.returncode,2,r.stderr);self.assertNotIn('Traceback',r.stderr)
                self.assertEqual(out.read_text(),'old graph');self.assertEqual(report.read_text(),'old report')
                self.assertTrue(source.is_symlink())

    def test_report_symlink_loop_refuses_before_graph_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv')
            out=base/'graph.json';out.write_text('old graph')
            report=base/'loop';report.symlink_to(report.name)
            r=self.command('csv','unified',path,out,report)
            self.assertEqual(r.returncode,2,r.stderr);self.assertNotIn('Traceback',r.stderr)
            self.assertEqual(out.read_text(),'old graph');self.assertTrue(report.is_symlink())

    def test_same_inode_different_name_is_guarded_before_build_model(self):
        import csv_adapter
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,path,manifest=self.fixture(base,'csv');alias=base/'hard';os.link(path,alias)
            with patch.object(sys,'argv',['csv_adapter',str(path),'--output',str(alias)]),patch.object(csv_adapter,'build_model',side_effect=AssertionError('must not build')):
                with self.assertRaises(SystemExit) as raised:csv_adapter.main()
            self.assertEqual(raised.exception.code,2)


if __name__=='__main__':unittest.main()
