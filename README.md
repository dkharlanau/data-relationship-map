# Data Relationship Map

Visualize cross-system business-object relationships, identifiers, dependencies, and broken links from ordinary data exports.

## Problem

Consultants often need to understand relationships across customer IDs, BP IDs, suppliers, materials, partner functions, organizational structures, and cross-system keys.

## Core idea

Ingest ordinary data exports (customers.xlsx, partners.xlsx, sales-areas.xlsx, crosswalk.xlsx) and build a relationship graph across cross-system identifiers.

## Example

```text
Legacy Customer 4711
  -> MDG BP 7200311
  -> S4 BP 10000345
  -> Ship-To 10000891
  -> Payer 10000345
```

## Initial scope

- multi-file relationship ingestion
- configurable keys
- graph generation
- broken-reference detection
- orphan detection
- duplicate relationship detection
- interactive object view
- cross-system ID paths

## Long-term direction

A portable relationship model for enterprise/master data analysis.

## Design principles

- versionable
- portable
- machine-readable
- deterministic-first
- visual where useful
- Git-friendly
- vendor-neutral where practical
- interoperable with enterprise tools

## Status

Planning.
