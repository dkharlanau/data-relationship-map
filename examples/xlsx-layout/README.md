# Do not import an identity from ambiguous cell positions

These small generated workbooks contain synthetic customer IDs, not project data.
They demonstrate why coordinate errors must stop an import before a value is lost.

```sh
python examples/xlsx-layout/generate.py /tmp/drm-coordinate-examples
# The destination must not exist.
data-relationship-map import-xlsx /tmp/drm-coordinate-examples/valid.json \
  --output /tmp/coordinate-model.json --import-report /tmp/coordinate-report.json
# Exit 0. One node: SYNTHETIC:00120.
data-relationship-map import-xlsx /tmp/drm-coordinate-examples/duplicate-cell.json \
  --output /tmp/coordinate-model.json --import-report /tmp/coordinate-error.json
# Exit 2. The previous model file is retained, not revalidated.
```

The duplicate case places both `00120` and `00999` at `A2`. A dictionary assignment
used to keep the last value and report a complete import. The guarded importer
rejects the row instead. `wrong-row.json` puts `A9` inside row 2; its provenance
cannot honestly be called row 2. `missing-reference.json` omits the cell position;
it must not silently become a skipped blank record.

With an import report, each of these known row-2 errors is one rejected record,
`status: aborted`, and `model_returned: false`. No complete new graph is returned.
Do not resolve provisional output references against an old graph or mistake the
retained old file for a successful new import. See
[the accounting contract](../../docs/import-accounting.md#xlsx-coordinate-integrity).

The parser requires explicit, consistent row/cell positions. This is a declared
supported-input subset, not a claim that every spreadsheet with omitted XML
coordinates is invalid in Excel. Re-export unsupported input with explicit
coordinates; the importer does not guess or repair them. No live SAP behavior,
identity correctness or spreadsheet-application visual validation is demonstrated.
