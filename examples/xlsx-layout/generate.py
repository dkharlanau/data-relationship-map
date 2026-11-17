"""Create synthetic XLSX coordinate examples in a new local directory."""
import argparse
import json
from pathlib import Path
import zipfile

MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'


def generate(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for case in ('valid', 'duplicate-cell', 'wrong-row', 'missing-reference'):
        reference = '' if case == 'missing-reference' else ' r="A9"' if case == 'wrong-row' else ' r="A2"'
        first = f'<c{reference} t="inlineStr"><is><t>00120</t></is></c>'
        duplicate = '<c r="A2" t="inlineStr"><is><t>00999</t></is></c>' if case == 'duplicate-cell' else ''
        parts = {
            '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
            '_rels/.rels': f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
            'xl/workbook.xml': f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets><sheet name="Customers" sheetId="1" r:id="rId1"/></sheets></workbook>',
            'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
            'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{MAIN}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row><row r="2">{first}{duplicate}</row></sheetData></worksheet>',
        }
        with zipfile.ZipFile(destination / f'{case}.xlsx', 'w', zipfile.ZIP_DEFLATED) as book:
            for name, content in parts.items():
                book.writestr(name, content)
        manifest = {'node_sources': [{'file': f'{case}.xlsx', 'sheet': 'Customers', 'id': 'SYNTHETIC:{ID}', 'system': 'SYNTHETIC', 'object': 'customer'}]}
        (destination / f'{case}.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path, help='A directory that does not yet exist')
    args = parser.parse_args()
    generate(args.destination)
    print(f'Created four synthetic workbook/manifest pairs in {args.destination}')
