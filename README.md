# Data Relationship Map

Turn ordinary enterprise exports into a traceable cross-system relationship graph for identity, linkage, lineage, and broken-reference investigations.

## Why this exists

Enterprise data investigations often start with several Excel/CSV extracts and a deceptively simple question: **how is this object related across systems?** Customer IDs, BP IDs, partner functions, organizational assignments, suppliers, materials, and legacy identifiers quickly become an implicit graph that is hard to inspect and easy to break.

Data Relationship Map makes that graph explicit, testable, and explainable back to the source export.

## Current capabilities

- ingest CSV and `.xlsx` exports through small manifests
- read XLSX worksheets using the Python standard library; no Excel runtime dependency
- build composite IDs directly from columns
- apply explicit normalization rules: `strip`, `upper`, `lower`, `strip_leading_zeros`
- normalize into a vendor-neutral canonical graph
- preserve file/sheet/row provenance
- expose normalized identity collisions instead of silently merging them
- surface conflicting attributes when the same canonical ID has inconsistent metadata
- detect broken references, duplicate nodes/relationships, and orphans
- find the shortest cross-system path between identifiers
- compare graph snapshots and report relationship/orphan drift
- run the same checks automatically in GitHub Actions

## Quick start

Analyze a canonical graph:

```bash
python relationship_map.py examples/customer-chain.json validate
python relationship_map.py examples/customer-chain.json path AFS:4711 S4:10000891
```

Build it from CSV:

```bash
python csv_adapter.py examples/csv/manifest.json --output customer-model.json
python relationship_map.py customer-model.json validate
```

Build it from XLSX. The repository generates a small synthetic workbook for the example/CI path:

```bash
python examples/xlsx/make_sample.py examples/xlsx/customer_crosswalk.xlsx
python xlsx_adapter.py examples/xlsx/manifest.json --output customer-xlsx-model.json
python relationship_map.py customer-xlsx-model.json path AFS:4711 S4:10000345
```

Compare two snapshots:

```bash
python relationship_diff.py examples/customer-chain.json examples/customer-chain-after.json
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

## Composite keys and normalization

Templates can use several export columns:

```json
{
  "file": "customers.xlsx",
  "sheet": "Customers",
  "id": "KNVP:{KUNNR}:{VKORG}:{VTWEG}:{SPART}:{PARVW}",
  "normalizers": {
    "KUNNR": ["strip", "strip_leading_zeros"],
    "PARVW": "upper"
  }
}
```

Normalization is explicit rather than automatic. If two raw identities normalize to the same canonical ID, the node contains `identity_collisions` plus source provenance so the merge can be investigated.

## CSV manifest

```json
{
  "node_sources": [
    {"file": "customer_crosswalk.csv", "id": "AFS:{AFS_KUNNR}", "system": "AFS", "object": "customer"},
    {"file": "customer_crosswalk.csv", "id": "MDG:{MDG_BP}", "system": "MDG", "object": "business-partner"}
  ],
  "relationship_sources": [
    {"file": "customer_crosswalk.csv", "from": "AFS:{AFS_KUNNR}", "to": "MDG:{MDG_BP}", "type": "mapped_to"}
  ]
}
```

Source-specific exports stay at the boundary while analysis remains reusable outside SAP.

## Canonical model

```json
{
  "nodes": [
    {
      "id": "AFS:4711",
      "system": "AFS",
      "object": "customer",
      "provenance": [{"file": "customer_crosswalk.xlsx", "sheet": "Crosswalk", "row": 2}]
    }
  ],
  "relationships": [
    {
      "from": "AFS:4711",
      "to": "MDG:7200311",
      "type": "mapped_to",
      "provenance": {"file": "customer_crosswalk.xlsx", "sheet": "Crosswalk", "row": 2}
    }
  ]
}
```

## Product direction

1. Many-to-one / one-to-many ambiguity diagnostics beyond normalization collisions.
2. Directed lineage and impact queries.
3. Multi-file investigation summaries and deterministic prioritization.
4. Export into the shared browser graph explorer.
5. Reconciliation-as-Code integration for expected-vs-observed links.
6. Enterprise Change Graph integration for impact propagation.

## Design principles

- versionable
- portable
- machine-readable
- deterministic-first
- provenance-preserving
- explicit normalization
- Git-friendly
- vendor-neutral where practical
- synthetic examples safe to publish

## Related projects

- [Mapping as Code](https://github.com/dkharlanau/mapping-as-code)
- [Transformation Graph](https://github.com/dkharlanau/transformation-graph)
- [Interface as Code](https://github.com/dkharlanau/interface-as-code)
- [Reconciliation as Code](https://github.com/dkharlanau/reconciliation-as-code)
- [Process as Code](https://github.com/dkharlanau/process-as-code)
- [Enterprise Change Graph](https://github.com/dkharlanau/enterprise-change-graph)
- [Decision Tables as Code](https://github.com/dkharlanau/decision-tables-as-code)
- [Cutover Graph](https://github.com/dkharlanau/cutover-graph)
- [Project Evidence Graph](https://github.com/dkharlanau/project-evidence-graph)

## Status

**MVP / active development.** CSV/XLSX ingestion, composite keys, normalization, provenance, collision diagnostics, graph validation, path analysis, snapshot drift, examples, tests, and CI are implemented.
