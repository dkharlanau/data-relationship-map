# Agent Development Contract

## Product objective

Turn ordinary enterprise data exports into a deterministic cross-system relationship model that helps investigate identity, linkage, lineage, and broken-reference problems.

## Work loop

1. Pick the highest-value unfinished item in `ROADMAP.md`.
2. Implement the smallest complete vertical slice.
3. Add or update a realistic fixture.
4. Add tests for success and failure cases.
5. Run the full test suite and CLI example.
6. Update README/ROADMAP only when behavior actually exists.
7. Prefer extending the canonical model over adding source-specific logic to the core.

## Commands

```bash
python -m unittest discover -s tests -v
python relationship_map.py examples/customer-chain.json validate
python csv_adapter.py examples/csv/manifest.json --output /tmp/customer-model.json
python relationship_map.py /tmp/customer-model.json validate
```

## Invariants

- deterministic output for identical input
- source adapters stay outside the graph-analysis core
- no SAP-specific assumption is required by the canonical model
- invalid/broken input must be reported, not silently repaired
- IDs are stable strings
- new dependencies require a clear product benefit
- examples must be synthetic and safe to publish

## Definition of done

A change is complete only when executable behavior, tests, example data, and user-facing documentation agree.
