import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from test_xlsx_adapter import write_minimal_xlsx
from xlsx_adapter import build_model, read_sheet, _cell_position

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
ROOT = Path(__file__).resolve().parents[1]


def modify(path, operation):
    with zipfile.ZipFile(path) as z:
        parts = {name: z.read(name) for name in z.namelist()}
    root = ET.fromstring(parts['xl/worksheets/sheet1.xml'])
    operation(root.findall('.//' + NS + 'row'))
    parts['xl/worksheets/sheet1.xml'] = ET.tostring(root)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in parts.items():
            z.writestr(name, content)


def duplicate(rows, index=1):
    cell = ET.fromstring(ET.tostring(rows[index][0]))
    cell.find('.//' + NS + 't').text = 'WRONG'
    rows[index].append(cell)


class XlsxCoordinateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.path = self.base / 'source.xlsx'
        write_minimal_xlsx(self.path, [['ID'], ['A'], ['B']])
        self.manifest = {'node_sources': [{'file': self.path.name, 'sheet': 'Data', 'id': 'OBJ:{ID}'}]}

    def tearDown(self):
        self.tmp.cleanup()

    def reject(self, operation, reason):
        modify(self.path, operation)
        before = self.path.read_bytes()
        report = {}
        with self.assertRaises(ValueError):
            build_model(self.manifest, self.base, import_report=report)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(report['status'], 'aborted')
        self.assertFalse(report['complete'])
        self.assertFalse(report['model_returned'])
        self.assertEqual(report['counts'], {'encountered': 1, 'accepted': 0, 'skipped': 0, 'rejected': 1})
        self.assertEqual(report['sources'][0]['records'][0]['row'], 2)
        self.assertEqual(report['sources'][0]['records'][0]['reason'], reason)
        return report

    def test_duplicate_cell_does_not_overwrite_identity(self):
        self.reject(duplicate, 'duplicate_cell_coordinate')

    def test_case_equivalent_and_zero_padded_cell_duplicates_rejected(self):
        for ref in ('a2', 'A02'):
            with self.subTest(ref=ref):
                write_minimal_xlsx(self.path, [['ID'], ['A'], ['B']])
                def change(rows):
                    duplicate(rows); rows[1][-1].set('r', ref)
                self.reject(change, 'duplicate_cell_coordinate')

    def test_cell_row_must_match_enclosing_row(self):
        self.reject(lambda rows: rows[1][0].set('r', 'A9'), 'cell_row_mismatch')

    def test_missing_cell_reference_does_not_become_blank_record(self):
        self.reject(lambda rows: rows[1][0].attrib.pop('r'), 'missing_cell_reference')

    def test_invalid_cell_coordinates_are_contextual_rejections(self):
        for ref in ('A0', 'A1048577', 'XFE2', 'A-2', 'A2\n', '$A$2', 'A٢'):
            with self.subTest(ref=ref):
                write_minimal_xlsx(self.path, [['ID'], ['A'], ['B']])
                self.reject(lambda rows: rows[1][0].set('r', ref), 'invalid_cell_reference')

    def test_worksheet_coordinate_limits_are_bounded(self):
        self.assertEqual(_cell_position('XFD1048576'), (16383, 1048576))
        self.assertEqual(_cell_position('a02'), (0, 2))
        for ref in ('XFE1', 'A1048577', 'ZZZZZZ1'):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                _cell_position(ref)

    def test_invalid_row_coordinate_has_no_fabricated_record(self):
        for value in (None, '', '0', '-1', 'x', '1048577', '٢'):
            with self.subTest(value=value):
                write_minimal_xlsx(self.path, [['ID'], ['A'], ['B']])
                def change(rows):
                    if value is None: rows[1].attrib.pop('r')
                    else: rows[1].set('r', value)
                modify(self.path, change); report = {}
                with self.assertRaises(ValueError):build_model(self.manifest, self.base, import_report=report)
                self.assertEqual(report['counts']['encountered'], 0)
                self.assertEqual(report['sources'][0]['error'], 'source_or_contract_error')
                self.assertEqual(report['status'], 'aborted')

    def test_duplicate_or_decreasing_rows_preserve_partial_boundary(self):
        for position in ('2', '1'):
            with self.subTest(position=position):
                write_minimal_xlsx(self.path, [['ID'], ['A'], ['B']])
                modify(self.path, lambda rows: rows[2].set('r', position))
                report = {}
                with self.assertRaisesRegex(ValueError, 'unique and increasing'):
                    build_model(self.manifest, self.base, import_report=report)
                self.assertEqual(report['counts'], {'encountered': 1, 'accepted': 1, 'skipped': 0, 'rejected': 0})
                self.assertFalse(report['model_returned'])
                self.assertEqual(report['sources'][0]['error'], 'source_or_contract_error')

    def test_bad_header_coordinates_are_source_error_not_data_row(self):
        modify(self.path, lambda rows: duplicate(rows, 0)); report = {}
        with self.assertRaisesRegex(ValueError, 'duplicate cell'):
            build_model(self.manifest, self.base, import_report=report)
        self.assertEqual(report['counts']['encountered'], 0)
        self.assertEqual(report['sources'][0]['error'], 'source_or_contract_error')

    def test_sparse_rows_and_unordered_cells_remain_supported(self):
        write_minimal_xlsx(self.path, [['ID','LABEL'], ['A','Alpha']])
        def change(rows):
            rows[1].set('r', '7')
            for cell in rows[1]:cell.set('r',cell.attrib['r'][:-1]+'7')
            rows[1][:] = list(reversed(rows[1]))
        modify(self.path, change)
        rows = list(read_sheet(self.path, 'Data'))
        self.assertEqual(rows, [(7, {'ID': 'A', 'LABEL': 'Alpha'})])

    def test_blank_explicit_row_is_still_skipped(self):
        write_minimal_xlsx(self.path, [['ID'], [''], ['A']]); report = {}
        model = build_model(self.manifest, self.base, import_report=report)
        self.assertEqual([n['id'] for n in model['nodes']], ['OBJ:A'])
        self.assertEqual(report['counts']['skipped'], 1)
        self.assertEqual(report['status'], 'complete')

    def test_later_sources_stay_not_started_on_failure(self):
        duplicate_manifest = {'node_sources': self.manifest['node_sources'] * 2}
        modify(self.path, duplicate); report = {}
        with self.assertRaises(ValueError):build_model(duplicate_manifest, self.base, import_report=report)
        self.assertEqual(report['sources'][1]['status'], 'not_started')
        self.assertEqual(report['sources'][1]['counts']['encountered'], 0)

    def test_cli_rejects_layout_without_overwriting_existing_graph(self):
        modify(self.path, duplicate)
        manifest = self.base/'manifest.json'; manifest.write_text(json.dumps(self.manifest))
        output = self.base/'graph.json'; output.write_bytes(b'previous graph bytes\n')
        report = self.base/'report.json'
        p = subprocess.run([sys.executable,str(ROOT/'xlsx_adapter.py'),str(manifest),'--output',str(output),'--import-report',str(report)],capture_output=True,text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn('duplicate cell coordinate', p.stderr)
        self.assertNotIn('Traceback', p.stderr)
        self.assertEqual(output.read_bytes(), b'previous graph bytes\n')
        self.assertFalse(json.loads(report.read_text())['model_returned'])
        self.assertFalse(p.stdout)

    def test_cli_without_sidecar_also_rejects_layout(self):
        modify(self.path, duplicate)
        manifest = self.base/'manifest.json'; manifest.write_text(json.dumps(self.manifest))
        p = subprocess.run([sys.executable,str(ROOT/'xlsx_adapter.py'),str(manifest)],capture_output=True,text=True)
        self.assertEqual(p.returncode, 2)
        self.assertFalse(p.stdout)
        self.assertNotIn('Traceback', p.stderr)


if __name__ == '__main__':
    unittest.main()
