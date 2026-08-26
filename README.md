# Data Relationship Map

Visualize and validate cross-system business-object relationships, identifiers, dependencies, and broken links from ordinary enterprise data exports.

## Why this exists

Enterprise data investigations often start with several Excel/CSV extracts and a deceptively simple question: **how is this object related across systems?** Customer IDs, BP IDs, partner functions, organizational assignments, suppliers, materials, and legacy identifiers quickly turn into an implicit graph that is hard to inspect and easy to break.

Data Relationship Map makes that graph explicit and testable.

## Current MVP

The repository now includes a zero-dependency Python engine that can:

- validate node and relationship definitions
- detect broken references
- detect duplicate nodes and duplicate relationships
- identify orphan objects
- find the shortest cross-system path between two identifiers
- run the same checks automatically in GitHub Actions

## Quick start

```bash
python relationship_map.py examples/customer-chain.json validate
python relationship_map.py examples/customer-chain.json path AFS:4711 S4:10000891
python -m unittest discover -s tests -v
```

Expected path:

```text
AFS:4711 -> MDG:7200311 -> S4:10000345 -> S4:10000891
```

The example intentionally contains an unlinked S/4 customer so the analysis also demonstrates orphan detection.

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

The model is deliberately small. Source-specific Excel/CSV adapters can convert exports into this canonical representation without coupling the graph engine to SAP or any other platform.

## Product direction

Next layers are:

1. CSV/Excel adapters and configurable composite keys.
2. Relationship confidence and provenance.
3. Directed lineage and impact analysis.
4. HTML/Graphviz explorer for GitHub Pages.
5. Cross-file identity resolution.
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

**MVP / active development.** The canonical graph validator, path finder, example model, tests, and CI are implemented.
