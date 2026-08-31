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
- consolidated `investigate` report combining structural findings, supplied identity/cardinality policy, bounded upstream/downstream lineage and provenance
- deterministic JSON and reviewer-readable Markdown investigation output
- standalone dependency-free HTML investigation output generated from the same report
- bounded subgraph handoff with deterministic `pack_id`, JSON/Markdown/HTML review artifacts and SHA-256 manifest verification
- fail-loud investigation statuses: `clear`, `findings`, `invalid_model`, `invalid_focus`
- realistic AFS → MDG → S/4 examples
- unit tests and GitHub Actions CI, including installed-CLI smoke tests

## Now — finding severity and lifecycle policy

1. Add explicit deterministic finding severity/prioritization policy instead of introducing an opaque score.
2. Give findings a review lifecycle (`open`, `accepted`, `resolved`, `superseded`) without rewriting historical evidence.
3. Define compatibility rules for comparing finding identity across repeated bounded handoffs.

## Next — ecosystem integration

- emit Project Evidence Graph fragments so relationship findings can link to defects, changes, tests and evidence
- let Reconciliation as Code consume expected identity/cardinality relationships as explicit controls
- let Enterprise Change Graph consume bounded directional lineage as change-impact evidence
- derive relationship edges from Mapping as Code without copying mapping ownership into this repository
- expose the same investigation summary through the shared Visual Workbench rendering boundary

## Later — operational investigation

- compare expected cardinality with observed relationships across multiple snapshots
- freshness/authority metadata for imported extracts
- explicit resolution lifecycle across repeated imports and snapshots
- optional adapters for governed source systems when repeated real investigations justify them

## Product test

A consultant should be able to take ordinary CSV/Excel project exports and answer, without writing custom code:

> Where did this object come from, what can it affect downstream, what changed, what is ambiguous or broken, which source records prove that conclusion, which findings matter first, and what bounded evidence should be handed to the next assurance or change-analysis tool?
