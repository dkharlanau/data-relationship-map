# Roadmap

## Done — usable MVP

- canonical node/relationship model
- deterministic validation
- broken-reference, duplicate, and orphan detection
- shortest cross-system identity path
- strict downstream and upstream lineage traversal
- system/object boundary stops and max-depth impact limits
- provenance-preserving lineage edges and deterministic paths
- CSV export adapter with manifest-driven field mapping
- XLSX worksheet adapter with zero runtime dependencies
- composite ID templates and explicit key normalization
- file/sheet/row provenance
- normalized identity collision diagnostics
- conflicting metadata detection for repeated IDs
- explicit relationship-cardinality policy
- one-to-many / many-to-one ambiguity diagnostics
- graph snapshot diff with relationship/orphan drift
- realistic AFS -> MDG -> S/4 examples
- unit tests and GitHub Actions CI

## Now — make investigations composable

1. Merge several crosswalk/partner/org extracts into one investigation model.
2. Add deterministic severity/prioritization for relationship findings.
3. Emit stable `eac://` artifact references for nodes, relationships, and findings.

## Next — investigation workbench

- produce a concise investigation summary with source references
- export a browser-ready graph for the shared enterprise graph explorer
- compare expected cardinality with observed relationships across snapshots
- package a bounded upstream/downstream subgraph for another agent/tool

## Later — ecosystem integration

- Mapping as Code: derive mapping relationships
- Reconciliation as Code: expected-vs-observed relationship controls
- Enterprise Change Graph: impact propagation
- Project Evidence Graph: link findings to defects, changes, tests, and evidence

## Product test

A consultant should be able to take ordinary CSV/Excel project exports and answer, without writing custom code:

> Where did this object come from, what can it affect downstream, what changed, what is ambiguous or broken, and which source records should I investigate first?
