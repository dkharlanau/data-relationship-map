# Data Relationship Map

Turn ordinary enterprise exports into a traceable cross-system relationship graph for identity, linkage, lineage, and broken-reference investigations.

## Why this exists

Enterprise data investigations often start with several Excel/CSV extracts and a deceptively simple question: **how is this object related across systems?** Customer IDs, BP IDs, partner functions, organizational assignments, suppliers, materials, and legacy identifiers quickly become an implicit graph that is hard to inspect and easy to break.

Data Relationship Map makes that graph explicit, testable, and explainable back to the source export.

## Current capabilities

- ingest ordinary CSV exports through a small manifest
- normalize them into a vendor-neutral canonical graph
- preserve source file + row provenance
- surface conflicting attributes when the same ID appears with inconsistent metadata
- detect broken references, duplicate nodes/relationships, and orphans
- find the shortest cross-system path between identifiers
- compare two graph snapshots and report relationship drift
- detect newly created and resolved orphans
- run the same checks automatically in GitHub Actions

## Quick start

Analyze a canonical graph:

```bash
python relationship_map.py examples/customer-chain.json validate
python relationship_map.py examples/customer-chain.json path AFS:4711 S4:10000891
```

Build it from a CSV crosswalk:

```bash
python csv_adapter.py examples/csv/manifest.json --output customer-model.json
python relationship_map.py customer-model.json validate
python relationship_map.py customer-model.json path AFS:4711 S4:10000345
```

Compare two snapshots:

```bash
python relationship_diff.py examples/customer-chain.json examples/customer-chain-after.json
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

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
      "provenance": [{"file": "customer_crosswalk.csv", "row": 2}]
    }
  ],
  "relationships": [
    {
      "from": "AFS:4711",
      "to": "MDG:7200311",
      "type": "mapped_to",
      "provenance": {"file": "customer_crosswalk.csv", "row": 2}
    }
  ]
}
```

## Product direction

1. `.xlsx` ingestion and composite/normalized keys.
2. Many-to-one / one-to-many ambiguity diagnostics.
3. Directed lineage and impact queries.
4. Multi-file investigation summaries and prioritization.
5. Export into the shared browser graph explorer.
6. Reconciliation-as-Code integration for expected-vs-observed links.
7. Enterprise Change Graph integration for impact propagation.

## Design principles

- versionable
- portable
- machine-readable
- deterministic-first
- provenance-preserving
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

**MVP / active development.** CSV ingestion, provenance, graph validation, path analysis, snapshot drift, examples, tests, and CI are implemented.
