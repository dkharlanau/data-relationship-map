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
- enforce explicit relationship-cardinality policy such as 1:1 identity mappings
- diagnose one-to-many and many-to-one ambiguity with the exact related IDs
- find the shortest cross-system path between identifiers
- compare graph snapshots and report relationship/orphan drift
- run the same checks automatically in GitHub Actions

## Quick start

Analyze a canonical graph:

```bash
python relationship_map.py examples/customer-chain.json validate
python relationship_map.py examples/customer-chain.json path AFS:4711 S4:10000891
python relationship_policy.py examples/customer-chain.json examples/identity-policy.json
```

Build it from CSV:

```bash
python csv_adapter.py examples/csv/manifest.json --output customer-model.json
python relationship_map.py customer-model.json validate
python relationship_policy.py customer-model.json examples/identity-policy.json
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

## Cardinality and ambiguity policy

A graph can be structurally valid while still being suspicious. For example, a legacy customer may unexpectedly map to two target BPs, or two source IDs may converge into one target where the mapping is expected to be 1:1.

```json
{
  "relationship_rules": {
    "mapped_to": {"max_outgoing": 1, "max_incoming": 1},
    "replicated_to": {"max_outgoing": 1, "max_incoming": 1}
  },
  "report_identity_collisions": true,
  "fail_on_identity_collisions": true
}
```

Rules are explicit per relationship type; relationships such as `ship_to` can remain unrestricted. The command exits non-zero when the configured policy is violated and returns the source/target IDs involved in each ambiguity.

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

1. Directed lineage and impact queries.
2. Merge several crosswalk/partner/org extracts into one investigation model.
3. Deterministic severity/prioritization for findings.
4. Investigation summaries with source references.
5. Export into the shared browser graph explorer.
6. Reconciliation-as-Code integration for expected-vs-observed links.
7. Enterprise Change Graph integration for impact propagation.

## Design principles

- versionable
- portable
- machine-readable
- deterministic-first
- provenance-preserving
- explicit normalization and relationship policy
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

**MVP / active development.** CSV/XLSX ingestion, composite keys, normalization, provenance, collision/cardinality diagnostics, graph validation, path analysis, snapshot drift, examples, tests, and CI are implemented.
