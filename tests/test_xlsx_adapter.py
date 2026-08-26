import html
import tempfile
import unittest
import zipfile
from pathlib import Path

from relationship_map import analyze, shortest_path
from xlsx_adapter import build_model, read_sheet


def _column_name(index: int) -> str:
    result = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def write_minimal_xlsx(path: Path, rows, sheet_name="Data"):
    sheet_rows = []
    for row_index, values in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(values):
            ref = f"{_column_name(col_index)}{row_index}"
            text = html.escape(str(value), quote=False)
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{html.escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", content_types)
        book.writestr("_rels/.rels", root_rels)
        book.writestr("xl/workbook.xml", workbook_xml)
        book.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        book.writestr("xl/worksheets/sheet1.xml", sheet_xml)


class XlsxAdapterTests(unittest.TestCase):
    def test_builds_relationship_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_minimal_xlsx(base / "crosswalk.xlsx", [
                ["AFS", "MDG", "S4"],
                ["4711", "7200311", "10000345"],
            ])
            manifest = {
                "node_sources": [
                    {"file": "crosswalk.xlsx", "sheet": "Data", "id": "AFS:{AFS}", "system": "AFS", "object": "customer"},
                    {"file": "crosswalk.xlsx", "sheet": "Data", "id": "MDG:{MDG}", "system": "MDG", "object": "business-partner"},
                    {"file": "crosswalk.xlsx", "sheet": "Data", "id": "S4:{S4}", "system": "S4", "object": "business-partner"},
                ],
                "relationship_sources": [
                    {"file": "crosswalk.xlsx", "sheet": "Data", "from": "AFS:{AFS}", "to": "MDG:{MDG}", "type": "mapped_to"},
                    {"file": "crosswalk.xlsx", "sheet": "Data", "from": "MDG:{MDG}", "to": "S4:{S4}", "type": "replicated_to"},
                ],
            }
            model = build_model(manifest, base)
            self.assertTrue(analyze(model)["valid"])
            self.assertEqual(shortest_path(model, "AFS:4711", "S4:10000345"), ["AFS:4711", "MDG:7200311", "S4:10000345"])
            self.assertEqual(model["nodes"][0]["provenance"], [{"file": "crosswalk.xlsx", "sheet": "Data", "row": 2}])

    def test_composite_key_normalization_exposes_identity_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_minimal_xlsx(base / "customers.xlsx", [
                ["KUNNR", "VKORG", "LABEL"],
                ["0004711", "1000", "Customer One"],
                ["4711", "1000", "Customer 1"],
            ])
            manifest = {
                "node_sources": [{
                    "file": "customers.xlsx",
                    "sheet": "Data",
                    "id": "S4:{KUNNR}:{VKORG}",
                    "system": "S4",
                    "object": "customer-sales-area",
                    "label": "{LABEL}",
                    "normalizers": {"KUNNR": ["strip", "strip_leading_zeros"]},
                }]
            }
            model = build_model(manifest, base)
            self.assertEqual(len(model["nodes"]), 1)
            node = model["nodes"][0]
            self.assertEqual(node["id"], "S4:4711:1000")
            self.assertEqual(node["identity_collisions"], ["S4:0004711:1000", "S4:4711:1000"])
            self.assertEqual(node["conflicts"]["label"], ["Customer 1", "Customer One"])
            self.assertEqual(node["provenance"][0]["normalization"]["KUNNR"], {"from": "0004711", "to": "4711"})

    def test_global_and_source_normalizers_compose(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_minimal_xlsx(base / "objects.xlsx", [["ID", "ORG"], [" ab-1 ", "de01"]])
            manifest = {
                "normalizers": {"ID": "strip"},
                "node_sources": [{
                    "file": "objects.xlsx", "sheet": "Data", "id": "OBJ:{ID}:{ORG}",
                    "normalizers": {"ID": "upper", "ORG": "upper"},
                }],
            }
            model = build_model(manifest, base)
            self.assertEqual(model["nodes"][0]["id"], "OBJ:AB-1:DE01")

    def test_missing_sheet_is_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_minimal_xlsx(base / "objects.xlsx", [["ID"], ["1"]])
            with self.assertRaisesRegex(ValueError, "worksheet 'Missing' not found"):
                list(read_sheet(base / "objects.xlsx", "Missing"))

    def test_missing_normalized_column_is_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_minimal_xlsx(base / "objects.xlsx", [["ID"], ["1"]])
            manifest = {"node_sources": [{
                "file": "objects.xlsx", "sheet": "Data", "id": "OBJ:{ID}",
                "normalizers": {"MISSING": "upper"},
            }]}
            with self.assertRaisesRegex(ValueError, "missing column"):
                build_model(manifest, base)


if __name__ == "__main__":
    unittest.main()
