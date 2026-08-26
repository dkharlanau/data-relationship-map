# Roadmap

## Done — usable MVP

- canonical node/relationship model
- deterministic validation
- broken-reference, duplicate, and orphan detection
- shortest cross-system identity path
- CSV export adapter with manifest-driven field mapping
- source file/row provenance
- conflicting metadata detection for repeated IDs
- graph snapshot diff with relationship/orphan drift
- realistic AFS -> MDG -> S/4 examples
- unit tests and GitHub Actions CI

## Now — make ordinary project exports useful

1. Add `.xlsx` ingestion without changing the canonical model.
2. Support composite identifiers and normalized key functions.
3. Detect ambiguous identity links and many-to-one / one-to-many anomalies.
4. Add directed lineage/impact queries in addition to undirected path finding.
5. Merge several crosswalk/partner/org extracts into one investigation model.

## Next — investigation workbench

- prioritize orphan/broken/ambiguous objects by deterministic severity
- produce a concise investigation summary with source references
- export a browser-ready graph for the shared enterprise graph explorer
- configurable rules for relationship expectations

## Later — ecosystem integration

- Mapping as Code: derive mapping relationships
- Reconciliation as Code: expected-vs-observed relationship controls
- Enterprise Change Graph: impact propagation
- Project Evidence Graph: link findings to defects, changes, tests, and evidence

## Product test

A consultant should be able to take ordinary project exports and answer, without writing custom code:

> Where did this object come from, what is it linked to across systems, what changed, what is broken, and which source records should I investigate first?
