# See what happened to each imported record

A relationship graph is a useful result, but it does not explain all the input
that produced it. An optional sidecar makes blank padding, repeated support and
rejected records visible without putting importer state into the canonical graph.

```sh
data-relationship-map import-csv examples/import-accounting/manifest.json \
  --output /tmp/model.json --import-report /tmp/import-report.json
data-relationship-map validate /tmp/model.json
# Expected exit 1: this fixture deliberately retains a duplicate relationship.
```

The same `--import-report` option is available on `import-xlsx` and both standalone
adapter scripts. The Python function remains `build_model(manifest, base_dir)`;
pass an empty dictionary as `import_report=report` to collect the same report.
The dictionary is populated in place and cleared before use. No flag or keyword
means the existing model-only interface, with the same strict identity checks.

## A small investigation, not a claim about SAP extraction

The synthetic example contains five objects. S4:100:0004711 and S4:200:0004711
remain different objects even though the displayed number is the same. A declared
crosswalk links one S/4 object to an MDG object. Two sold-to/ship-to relationships
use a different type, with sales-organization context explicitly in that type.
They do not assert identity equivalence. A repeated partner row remains a separate
relationship with its original provenance; it is not silently discarded.

The example returns five nodes, four relationships, and ten source-record
applications: nine accepted, one skipped blank record, zero rejected. The adapter
does not apply identity/cardinality policy itself. Use an explicit policy for the
relevant relation types before interpreting a one-to-many result as a finding.
The existing graph validator intentionally reports the duplicate relationship at
index 3 and exits 1. It also lists the other-client object as an orphan. Successful
import accounting is not a clean graph-validation result; do not delete evidence
to make validation green. Nothing in this fixture establishes a universal SAP
join or production behavior.

## What is counted

Report format: `data-relationship-map-import-report/1.0`.

The counting unit is **one parsed record applied to one source declaration**.
A file used by three declarations is read three times and counted three times.
This is intentional: one input record can produce two nodes and a relationship.
Totals are not distinct physical file rows. Each declaration has its own stable
position, such as `node_sources/0`, file, optional sheet and records.

- The header is excluded. CSV numbers are physical start/end lines; a quoted
  multiline record is one record spanning several lines.
- Empty CSV lines and all-blank data records are `skipped`, reason `blank_record`.
- XLSX counts explicit data-row elements after the header. Empty explicit rows
  are skipped; unmaterialized row-number gaps are not invented or counted. Blank
  XML rows before the header are outside the data-row scope.
- An accepted node records its final ID and `node_created` or `node_merged`.
  Relationship references contain the zero-based position in the final
  relationships array plus the exact endpoints and type. These are local model
  references, not newly minted canonical `eac://` identities.
- Each record has one disposition and zero or one output reference. Reusing a
  physical row through another declaration creates another ledger record.
- For every declaration and overall, encountered = accepted + skipped + rejected.

The optional report retains one entry per encountered source-declaration record in
memory. Large exports require proportionally more memory; this is not streaming
report delivery or an untrusted-file resource-limit mechanism.

The sidecar includes identity references and source filenames, but does not copy
labels, notes or complete raw rows. Treat it as potentially sensitive project data.

## When import stops

```sh
data-relationship-map import-csv examples/import-accounting/manifest-invalid.json \
  --output /tmp/model.json --import-report /tmp/partial-import-report.json
# Exit 2. A previously existing model.json is retained, not newly validated.
```

The importer still stops at the first error. In this example it records seven
accepted applications and one rejected record, then stops. The report has
`status: aborted`, `complete: false`, and `model_returned: false`. Rows beyond the
error are unknown, not skipped or accepted. Later declarations remain
`not_started`. Accepted output references in an aborted report are provisional:
no complete model was returned and they must not be resolved against an old graph.

Stable rejection reasons distinguish blank node IDs, blank relationship endpoints,
blank declared identity components and missing template columns. Other invalid
records use `invalid_record`. Header, source-opening and contract errors have a
source-level marker rather than a fabricated data row. The CLI retains the normal
error text separately. The report is a bounded failure receipt, not a collect-all
quarantine workflow. It cannot enumerate records that the parser never reached.

Always check the command's exit status. A manifest error or output-path failure can
leave an old sidecar untouched. Graph/report paths must differ and must not alias
the manifest or an input, including existing hardlinks and symlinks. The sidecar is
replaced atomically before the graph is written, but the two files are not a
transactional pair. A complete report describes model construction, not successful
graph-file delivery. Output I/O failure must not be interpreted as import approval.
The path check does not protect against hostile concurrent path replacement.

## Evidence boundary

This sidecar is **outside the canonical graph and bounded-handoff manifest**.
Existing handoff verification does not cover it. It proves neither authentic source
collection, identity correctness, freshness nor migration approval. Do not infer
that a graph with no rejected imports has no broken references or policy findings.

Issue #8 still needs owner review of the counting/status contract and the wider
investigation workflow. This first version deliberately retains fail-fast import,
not a partial-graph acceptance mode. Import-report success does not establish
operational acceptance or authorize a migration.

## Check the installed contract before integration

After installing the candidate package, run:

```sh
python scripts/check_import_report_contract.py
```

The standalone check launches the installed executable in a new temporary
directory, without importing project modules or test helpers. It exercises CSV
and XLSX dispositions, repeated declarations and relationship support, physical
multiline locations, exact model-byte compatibility, input-alias rejection,
partial failure and corrupt-workbook handling. Per-source counts must agree with
their records and sum to the global totals. Expected nonzero exits are checked
explicitly. The duplicate relationship deliberately remains a validation finding.
The local CI change runs this after installation, alongside the existing suite;
preparation and local execution do not mean GitHub Actions has run. Isolation is
checked for a normal installed wheel; an editable installation or an arbitrary
`--cli` executable can still load other code. This smoke check is not a general
validator for arbitrary reports or a proof of source authenticity.

## XLSX coordinate integrity

A source row can lose information before field mapping if its worksheet XML gives
two cells the same position. The adapter rejects duplicate cell coordinates,
cell/row mismatches, missing cell references and invalid coordinates before
constructing the row dictionary. It does not silently keep the last value or
count an unpositioned value as blank. Cell positions may be out of order within
a row; sparse rows remain supported.

The supported subset requires explicit positive decimal row numbers, unique and
increasing row order, and explicit cell references with a matching row number.
Worksheet limits are 1,048,576 rows and 16,384 columns. This bounds coordinate-based
allocation, not ZIP/XML resource usage in general. A valid XLSX producer may omit
some coordinates that a full spreadsheet application infers. This adapter does
not infer them; it rejects such input as unsupported rather than certifying a
possibly incorrect provenance. It is not a full OOXML conformance validator.

If a data row has a valid coordinate but its cells are ambiguous, its report entry
is rejected with an additive reason: `duplicate_cell_coordinate`,
`cell_row_mismatch`, `missing_cell_reference` or `invalid_cell_reference`.
Unreliable row numbering and header-layout errors use the existing source-level
`source_or_contract_error`; they do not invent an affected data-row number.
Previously encountered accepted records remain provisional after an abort, later
rows are unknown, and later source declarations stay `not_started`. Consumers
must handle new rejection reasons without treating an unrecognized reason as
acceptance. The report envelope and counting unit are unchanged.

The CLI exits 2, emits no complete new model and retains an existing graph file
when an import fails. This does not verify the old graph or make graph and report
a transactional pair. The same rejection applies when no sidecar is requested.
See the executable [coordinate examples](../examples/xlsx-layout/README.md).


## Protect input files even without a sidecar

The graph-only import route uses the same input/output alias guard as an import
with accounting. The graph and sidecar must differ from every declared source
and the manifest, and from each other. Existing symlinks, parent-directory
symlinks, relative aliases and hardlinks are compared before source rows are
read. If the check fails, exit 2 leaves existing graph/report/input bytes intact;
there is no partial-import ledger because import did not start.

For example, keep a synthetic export under an input directory and choose a
separate output name:

```bash
data-relationship-map import-csv examples/csv/manifest.json \
  --output /tmp/customer-relationship-graph.json
```

An explicitly chosen unrelated output remains replaceable. The check is not an
atomic transaction, a sandbox or a defence against another process swapping
paths after validation. It cannot protect a shell redirect that truncates an
input before the program starts. Prefer --output over redirection, preserve
original extracts and never infer that a retained old graph was revalidated.
