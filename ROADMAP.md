# Roadmap

## Done — usable investigation MVP

- canonical node/relationship model
- deterministic validation
- broken-reference, duplicate, and orphan detection
- shortest cross-system identity path
- strict downstream and upstream lineage traversal
- system/object boundary stops and max-depth impact limits
- provenance-preserving lineage edges and deterministic paths
- CSV export adapter with manifest-driven field mapping
- XLSX worksheet adapter with zero runtime dependencies
- multi-source manifests that merge several crosswalk/partner/org extracts into one canonical investigation model
- composite ID templates and explicit key normalization
- file/sheet/row provenance
- normalized identity collision diagnostics
- conflicting metadata detection for repeated IDs
- explicit relationship-cardinality policy
- one-to-many / many-to-one ambiguity diagnostics
- graph snapshot diff with relationship/orphan drift
- stable `eac://` references for objects, relationships, and policy findings
- machine-readable artifact index with preserved source provenance
- installable Python package and unified `data-relationship-map` command
- realistic AFS → MDG → S/4 examples
- unit tests and GitHub Actions CI, including installed-CLI smoke tests

## Now — investigation decision surface

1. Produce one concise investigation report that combines structural validation, identity/cardinality findings, lineage context, provenance and source rows.
2. Add deterministic prioritization for findings based on explicit policy rather than hidden scores.
3. Package a bounded upstream/downstream subgraph with stable references for another tool or agent.
4. Generate a browser-ready investigation view from the same bounded model rather than maintaining a separate visualization model.

## Next — ecosystem integration

- emit Project Evidence Graph fragments so relationship findings can link to defects, changes, tests and evidence
- let Reconciliation as Code consume expected identity/cardinality relationships as explicit controls
- let Enterprise Change Graph consume bounded directional lineage as change-impact evidence
- derive relationship edges from Mapping as Code without copying mapping ownership into this repository
- expose the same investigation summary through the shared Visual Workbench rendering boundary

## Later — operational investigation

- compare expected cardinality with observed relationships across multiple snapshots
- freshness/authority metadata for imported extracts
- explicit resolution lifecycle for findings rather than treating every historical anomaly as currently open
- optional adapters for governed source systems when repeated real investigations justify them

## Product test

A consultant should be able to take ordinary CSV/Excel project exports and answer, without writing custom code:

> Where did this object come from, what can it affect downstream, what changed, what is ambiguous or broken, which source records prove that conclusion, which findings matter first, and what bounded evidence should be handed to the next assurance or change-analysis tool?
