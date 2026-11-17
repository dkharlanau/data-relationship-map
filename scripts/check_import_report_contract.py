#!/usr/bin/env python3
"""Check the installed import CLI using synthetic data outside the source tree.

No project modules or test helpers are imported. Exit 0 means this bounded
contract check passed, not that the demonstrated graph is free of findings.
"""
from __future__ import annotations

import argparse
import csv
from html import escape
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


class ContractError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def validate_report(value: dict, counts: dict, status: str) -> dict:
    require(value.get('format') == 'data-relationship-map-import-report/1.0', 'wrong report format')
    require(value.get('counts') == counts, f'wrong report counts: {value.get("counts")}')
    require(value.get('status') == status, f'wrong report status: {value.get("status")}')
    require(value.get('complete') is (status == 'complete'), 'wrong completeness marker')
    require(value.get('model_returned') is (status == 'complete'), 'wrong model-returned marker')
    totals = dict(encountered=0, accepted=0, skipped=0, rejected=0)
    for source in value['sources']:
        actual = dict(encountered=len(source['records']), accepted=0, skipped=0, rejected=0)
        for record in source['records']:
            disposition = record['disposition']
            require(disposition in ('accepted', 'skipped', 'rejected'), 'unknown record disposition')
            actual[disposition] += 1
        declared = source['counts']
        require(set(declared) == set(actual), 'wrong source count fields')
        require(all(type(v) is int and v >= 0 for v in declared.values()), 'counts must be nonnegative integers')
        require(declared == actual, 'source counts do not describe its records')
        for key in totals:
            totals[key] += declared[key]
    require(all(type(v) is int and v >= 0 for v in value['counts'].values()), 'global counts must be nonnegative integers')
    require(totals == value['counts'], 'global totals do not reconcile with source counts')
    return value


def write_xlsx(path: Path, rows: list[list[str]]) -> None:
    """Small synthetic inline-string workbook; not an XLSX library replacement."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    data = []
    for number, values in enumerate(rows, 1):
        cells = ''.join(f'<c r="{chr(65+i)}{number}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
                        for i, v in enumerate(values))
        data.append(f'<row r="{number}">{cells}</row>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as book:
        book.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="Data" sheetId="1" r:id="r1"/></sheets></workbook>')
        book.writestr('xl/_rels/workbook.xml.rels', f'<Relationships xmlns="{package_rel}"><Relationship Id="r1" Target="worksheets/sheet1.xml" Type="{rel}/worksheet"/></Relationships>')
        book.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="{ns}"><sheetData>{"".join(data)}</sheetData></worksheet>')


def check(cli: Path) -> dict:
    checks = []
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    env['PYTHONSAFEPATH'] = '1'
    with tempfile.TemporaryDirectory(prefix='drm-import-contract-') as temporary:
        root = Path(temporary)

        def run(name: str, args: list[str | Path], expected: int) -> subprocess.CompletedProcess:
            result = subprocess.run([str(cli), *map(str, args)], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=30)
            require(result.returncode == expected,
                    f'{name}: expected exit {expected}, got {result.returncode}; stderr={result.stderr.strip()}')
            require('Traceback' not in result.stderr, f'{name}: unexpected traceback')
            checks.append({'name': name, 'exit': result.returncode, 'expected_exit': expected})
            return result

        def report(path: Path, counts: dict, status: str) -> dict:
            value = json.loads(path.read_text(encoding='utf-8'))
            return validate_report(value, counts, status)

        rows = [['FROM', 'TO', 'NOTE'], ['0001', '0002', 'first'],
                ['0001', '0003', 'line one\nline two'], ['0001', '0002', 'second support'], ['', '', '']]
        with (root/'records.csv').open('w', newline='', encoding='utf-8') as handle:
            csv.writer(handle).writerows(rows)
        sources = [dict(file='records.csv', id='{FROM}'), dict(file='records.csv', id='{TO}')]
        manifest = dict(node_sources=sources, relationship_sources=[{
            'file': 'records.csv', 'from': '{FROM}', 'to': '{TO}', 'type': 'sold_to_ship_to'}])
        path = root/'manifest.json'; path.write_text(json.dumps(manifest), encoding='utf-8')
        graph = root/'model.json'; ledger = root/'report.json'
        run('csv-complete', ['import-csv', path, '--output', graph, '--import-report', ledger], 0)
        complete = report(ledger, dict(encountered=12, accepted=9, skipped=3, rejected=0), 'complete')
        require(complete['sources'][0]['records'][1]['row'] == 3 and
                complete['sources'][0]['records'][1]['row_end'] == 4, 'lost CSV physical span')
        edges = complete['sources'][2]['records'][:3]
        require([r['outputs'][0]['index'] for r in edges] == [0, 1, 2], 'lost repeated edge references')
        require(edges[0]['outputs'][0]['to'] == edges[2]['outputs'][0]['to'] == '0002', 'lost duplicate support')
        retained = graph.read_bytes()
        run('csv-model-only', ['import-csv', path, '--output', root/'control.json'], 0)
        require((root/'control.json').read_bytes() == retained, 'sidecar changed canonical model bytes')
        validation = run('duplicate-remains-visible', ['validate', graph], 1)
        require(len(json.loads(validation.stdout)['duplicate_relationships']) == 1, 'duplicate was concealed')

        (root/'records.csv').write_text('FROM,TO,NOTE\n0001,0002,first\n,0003,missing identifier\n0004,0005,unvisited\n', encoding='utf-8')
        run('csv-aborted', ['import-csv', path, '--output', graph, '--import-report', ledger], 2)
        partial = report(ledger, dict(encountered=2, accepted=1, skipped=0, rejected=1), 'aborted')
        require([s['status'] for s in partial['sources']] == ['aborted','not_started','not_started'], 'unvisited declarations misrepresented')
        require(graph.read_bytes() == retained, 'failed import replaced retained graph')
        before = (root/'records.csv').read_bytes()
        run('input-alias-rejected', ['import-csv', path, '--output', graph, '--import-report', root/'records.csv'], 2)
        require((root/'records.csv').read_bytes() == before, 'source overwritten')

        write_xlsx(root/'records.xlsx', [['ID','LABEL'],['001','first'],[],['001','repeat']])
        path.write_text(json.dumps({'node_sources':[{'file':'records.xlsx','sheet':'Data','id':'{ID}'}]}), encoding='utf-8')
        run('xlsx-complete', ['import-xlsx', path, '--output', graph, '--import-report', ledger], 0)
        xlsx = report(ledger, dict(encountered=3,accepted=2,skipped=1,rejected=0), 'complete')
        require(xlsx['sources'][0]['sheet'] == 'Data', 'lost worksheet provenance')
        require([r['reason'] for r in xlsx['sources'][0]['records']] == ['node_created','blank_record','node_merged'], 'wrong XLSX dispositions')
        retained = graph.read_bytes(); (root/'records.xlsx').write_text('not an archive', encoding='utf-8')
        run('xlsx-corruption-aborted', ['import-xlsx', path, '--output', graph, '--import-report', ledger], 2)
        report(ledger,dict(encountered=0,accepted=0,skipped=0,rejected=0),'aborted')
        require(graph.read_bytes() == retained, 'corrupt workbook replaced retained graph')

    return {'status':'passed', 'checks':checks, 'scope':'synthetic installed CLI import-report contract',
            'remote_ci_executed':False, 'business_or_migration_approval':False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', default=shutil.which('data-relationship-map'), help='Installed executable, default: PATH lookup')
    args = parser.parse_args()
    if not args.cli:
        parser.error('Install data-relationship-map first or provide --cli')
    cli = Path(args.cli).expanduser().resolve()
    try:
        print(json.dumps(check(cli), indent=2))
    except (ContractError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f'Import contract check failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
