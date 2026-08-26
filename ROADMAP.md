# Roadmap

## Done — usable MVP

- canonical node/relationship model
- deterministic validation
- broken-reference, duplicate, and orphan detection
- shortest cross-system identity path
- CSV export adapter with manifest-driven field mapping
- realistic AFS -> MDG -> S/4 example
- unit tests and GitHub Actions CI

## Now — make ordinary project exports useful

1. Add `.xlsx` ingestion without changing the canonical model.
2. Support composite identifiers and normalized key functions.
3. Preserve provenance for every node/relationship: source file, row, column, timestamp.
4. Detect ambiguous identity links and many-to-one / one-to-many anomalies.
5. Add directed lineage/impact queries in addition to undirected path finding.

## Next — investigation workbench

- merge several crosswalk/partner/org extracts into one model
- compare two graph snapshots and explain relationship drift
- output reconciliation findings in machine-readable JSON
- generate an investigation summary for orphan/broken/ambiguous objects
- export a browser-ready graph for the shared enterprise graph explorer

## Later — ecosystem integration

- Mapping as Code: derive mapping relationships
- Reconciliation as Code: expected-vs-observed relationship controls
- Enterprise Change Graph: impact propagation
- Project Evidence Graph: link findings to defects, changes, tests, and evidence

## Product test

A consultant should be able to take ordinary project exports and answer, without writing custom code:

> Where did this object come from, what is it linked to across systems, what is broken, and which records should I investigate first?
