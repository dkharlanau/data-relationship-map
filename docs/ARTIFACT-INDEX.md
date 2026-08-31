# Data Relationship Artifact Index

`relationship_artifacts.py` publishes a stable logical identity layer over a Data Relationship Map model.

## Generate

```bash
python relationship_artifacts.py model.json \
  --policy examples/identity-policy.json \
  --observed-at 2026-08-25T10:00:00Z \
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

## Bounded, integrity-checked handoff

`data-relationship-map handoff build` writes the same contract as `artifact-index.json` inside a bounded handoff pack. The index is generated from the retained graph slice and supplied policy, so out-of-scope objects and findings remain out of scope. `--observed-at` stamps an explicit timezone-aware source observation time; the tool never substitutes its wall clock.

```bash
data-relationship-map handoff build model.json relationship-handoff/ \
  --policy examples/identity-policy.json \
  --focus AFS:4711 \
  --max-depth 2 \
  --observed-at 2026-08-25T10:00:00Z

data-relationship-map handoff verify relationship-handoff/
```

The pack manifest covers `artifact-index.json` by byte count and SHA-256, and pack identity includes its semantics. Current `0.2` packs include this file; the verifier remains compatible with retained `0.1` packs.

## Implemented Project Evidence Graph consumer

Project Evidence Graph imports the retained index without changing producer ownership:

```bash
project-evidence-graph import-relationship \
  relationship-handoff/artifact-index.json \
  --output project-relationship-evidence.json
```

Observed objects and relationships become external evidence; policy findings become external defects. Observation time is preserved. The adapter deliberately does not guess which project requirement or change the evidence belongs to.

Use separate virtual environments for the two installed MVP CLIs. They currently expose generic top-level Python module names that can collide in one environment. The tested integration boundary is the retained JSON artifact index, not a shared Python process or package environment.

## Boundary

The emitter and handoff builder have no runtime dependency on Project Evidence Graph. They expose stable domain artifacts; consumers decide which objects/findings matter to a wider project or assurance graph. The cross-repository workflow tests the current producer and consumer contract without moving semantic ownership into this repository.
