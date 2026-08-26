# Data Relationship Artifact Index

`relationship_artifacts.py` publishes a stable logical identity layer over a Data Relationship Map model.

## Generate

```bash
python relationship_artifacts.py model.json \
  --policy examples/identity-policy.json \
  --output relationship-artifacts.json
```

The contract is described by [`../schema/artifact-index.schema.json`](../schema/artifact-index.schema.json).

## Object refs

```text
eac://dkharlanau/data-relationship-map/object/<canonical-node-id>
```

Example:

```text
eac://dkharlanau/data-relationship-map/object/AFS:4711
```

The ref identifies the logical graph object. File, worksheet, row, and import-normalization metadata remain provenance and do not affect identity.

## Relationship refs

```text
eac://dkharlanau/data-relationship-map/relationship/<from-id>/<type>/<to-id>
```

A relationship artifact retains:

- source/target raw graph IDs;
- source/target object refs;
- relationship type;
- available source provenance.

Input row ordering does not affect the emitted relationship identity.

## Finding refs

When a relationship policy is supplied, deterministic diagnostics receive their own refs.

Cardinality:

```text
eac://dkharlanau/data-relationship-map/finding/cardinality/<relationship-type>/<direction>/<node-id>
```

Identity collision:

```text
eac://dkharlanau/data-relationship-map/finding/identity-collision/<node-id>
```

A finding can therefore be referenced by a defect, decision, test, or Project Evidence Graph node without copying the whole relationship model.

## Structural validity vs policy result

The artifact index keeps two separate signals:

- `valid` — whether the underlying relationship graph is structurally valid;
- `policy_passed` — whether the optional relationship/cardinality policy passed.

A valid graph containing a real one-to-many policy violation is still structurally valid. The finding is the result, not an artifact-index corruption.

## Boundary

This emitter has no dependency on Project Evidence Graph. It exposes stable domain artifacts; consumers decide which objects/findings matter to a wider project or assurance graph.
