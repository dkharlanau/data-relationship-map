# One identity, two supplied labels

A consultant receives two export rows for `LEGACY:100:0004711`. One calls the
account “North account”, the other “South account”. An explicit crosswalk links
it to `MDG:100:0009001`. The graph is structurally valid and there is only one
crosswalk target. That does not settle which supplied label should be used.

This synthetic case exercises the recorded-metadata-conflict slice of the
[Business Partner starter](https://github.com/dkharlanau/data-relationship-map/issues/6).
It uses configurable export columns, not SAP tables or a live connector. It does
not complete the other starter scenarios or its three practitioner reviews.

## Reproduce the investigation

From the repository root, after installing the package:

```bash
mkdir -p build/bp-conflict

data-relationship-map import-csv examples/bp-metadata-conflict/manifest.json \
  --output build/bp-conflict/graph.json \
  --import-report build/bp-conflict/import-report.json

data-relationship-map validate build/bp-conflict/graph.json

# Expected exit 1: usable graph with a recorded conflict, not a failed import.
data-relationship-map investigate build/bp-conflict/graph.json \
  --focus LEGACY:100:0004711 \
  --json-output build/bp-conflict/investigation.json \
  --markdown build/bp-conflict/investigation.md \
  --html build/bp-conflict/investigation.html

data-relationship-map handoff build build/bp-conflict/graph.json \
  build/bp-conflict/handoff --focus LEGACY:100:0004711 \
  --observed-at 2026-08-25T10:00:00Z

data-relationship-map handoff verify build/bp-conflict/handoff
```

The observation time above belongs to this authored fixture. It is not a
measurement of a real export's freshness. In an automated script, explicitly
handle the expected investigation exit 1 before continuing. Do not ignore an
unexpected exit 2 or reuse an old graph after an import failure.

## Read the result before making a decision

The import accounts for four source-declaration records: three object rows and
one crosswalk row, all accepted. The canonical model contains two nodes and one
relationship. The repeated legacy row is merged into the same explicit ID, with
both labels retained in `conflicts.label`. Leading zeros remain strings.

The investigation has:

- `status: findings`, with one `metadata_conflict_count`;
- structural validity still `true`, zero structural findings;
- the two supplied labels, without selecting a winner;
- contributing node provenance at `objects.csv` rows 2 and 4.

Those source references are the node's contributing rows. The current adapter
**does not retain a value-to-row mapping**. Do not claim that this report alone
proves which row supplied each individual value. Inspect the retained exports
when that attribution matters. The canonical node's first label remains for
backward compatibility; it is not endorsed as correct.

A useful next question for the data owner is: “Are these different observations
of one object, a stale description, or an incorrectly agreed key?” The tool does
not answer that business question or correct master data. Record the agreed
scope and evidence before changing the source or identity contract.

## Exact reporting contract

Recorded conflicts support the adapter's `system`, `object` and `label` fields.
Each field must contain an array with at least two distinct, nonblank strings.
Repeated identical entries do not increase the count. Values are sorted for
presentation, not ranked by authority. An empty conflict object adds no finding.
Malformed recorded conflicts stop investigation/handoff creation with exit 2
before output writes, including malformed conflicts elsewhere in the supplied
model. This prevents an incomplete interpretation from being silently cropped
away. It is not full canonical-model schema validation.

The count is **one per node and field**, not one per value or source row.
Conflict-bearing investigation JSON adds `metadata_conflicts` and
`summary.metadata_conflict_count`. No-conflict report contents and formats remain
unchanged. Graph validity, explicit cardinality policy and collision policy keep
their existing semantics. Invalid-focus/invalid-model status takes precedence.

A bounded handoff reevaluates the selected subgraph. Included conflicts remain
visible in its JSON, Markdown and HTML, and its manifest carries
`summary.metadata_conflicts`. Valid conflicts outside the selected scope are not
included. Inspect bounds before treating a scoped report as a whole-export audit.

## Handoff is not automatic assurance

The existing artifact index already preserves each object's raw `conflicts`.
This change does **not** map them to new index findings, severities, PEG defects
or requirement satisfaction. `artifact-index.valid: true` and even
`policy_passed: true` can coexist with recorded metadata conflicts. A consumer
must not read those fields as “all data conflicts resolved”.

Handoff verification checks retained integrity, not source truth, value-to-row
attribution, policy adequacy or business acceptance. The import sidecar remains
outside the handoff manifest. No SAP access, practitioner acceptance, performance
improvement or production result is claimed by this synthetic demonstration.
