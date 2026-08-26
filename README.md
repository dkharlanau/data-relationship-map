# Data Relationship Map

Visualize and validate cross-system business-object relationships, identifiers, dependencies, and broken links from ordinary enterprise data exports.

## Why this exists

Enterprise data investigations often start with several Excel/CSV extracts and a deceptively simple question: **how is this object related across systems?** Customer IDs, BP IDs, partner functions, organizational assignments, suppliers, materials, and legacy identifiers quickly turn into an implicit graph that is hard to inspect and easy to break.

Data Relationship Map makes that graph explicit and testable.

## Current MVP

The repository now includes a zero-dependency Python engine that can:

- ingest ordinary CSV exports through a small manifest
- normalize them into a canonical graph
- validate node and relationship definitions
- detect broken references
- detect duplicate nodes and duplicate relationships
- identify orphan objects
- find the shortest cross-system path between two identifiers
- run the same checks automatically in GitHub Actions

## Quick start

Analyze the bundled canonical example:

```bash
python relationship_map.py examples/customer-chain.json validate
python relationship_map.py examples/customer-chain.json path AFS:4711 S4:10000891
```

Build the graph from an ordinary CSV crosswalk first:

```bash
python csv_adapter.py examples/csv/manifest.json --output customer-model.json
python relationship_map.py customer-model.json validate
python relationship_map.py customer-model.json path AFS:4711 S4:10000345
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

## CSV manifest

A manifest maps CSV columns into canonical nodes and relationships without hard-coding SAP field names into the graph engine.

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

This keeps source-specific exports at the boundary while the relationship engine remains vendor-neutral.

## Canonical model

```json
{
  "nodes": [
    {"id": "AFS:4711", "system": "AFS", "object": "customer"},
    {"id": "MDG:7200311", "system": "MDG", "object": "business-partner"}
  ],
  "relationships": [
    {"from": "AFS:4711", "to": "MDG:7200311", "type": "mapped_to"}
  ]
}
```

## Product direction

1. Excel (`.xlsx`) adapter and configurable composite keys.
2. Relationship confidence and provenance.
3. Directed lineage and impact analysis.
4. HTML/Graphviz explorer for GitHub Pages.
5. Cross-file identity resolution and merge diagnostics.
6. Reconciliation-as-Code integration for expected-vs-observed links.
7. Enterprise Change Graph integration for impact propagation.

## Design principles

- versionable
- portable
- machine-readable
- deterministic-first
- visual where useful
- Git-friendly
- vendor-neutral where practical
- interoperable with enterprise tools

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

**MVP / active development.** CSV ingestion, canonical graph validation, path finding, examples, tests, and CI are implemented.
