# Do not turn a failed export refresh into new evidence

A consultant replaces yesterday's customer crosswalk with a new export. Today's
spreadsheet is malformed, so Data Relationship Map stops the import and preserves
the previous graph file. That is useful recovery behavior, but the file's continued
existence does **not** mean the new export was accepted. A script that blindly
exports that graph to Project Evidence Graph can misrepresent old data as a new
investigation.

The optional synthetic rehearsal makes the decision boundary executable. It does
not change either product's runtime or invent a new handoff format.

## Run the existing tools, with explicit checkpoints

Use trusted local installations of the prepared DRM and PEG versions in separate
virtual environments and a source checkout containing this script. No external
service or live SAP system is used. The historical public release wheels do not
include all the prepared changes tested here.

```bash
python scripts/rehearse_peg_handoff.py \
  --drm-cli /path/to/drm-env/bin/data-relationship-map \
  --peg-cli /path/to/peg-env/bin/project-evidence-graph \
  --output /tmp/new-relationship-review
```

The output directory must not exist. The runner only uses the bundled synthetic
crosswalk and coordinate examples. Paths identify trusted installed programs;
do not point them at executables from an unreviewed evidence bundle.

| Case | Producer result | Next action |
|---|---|---|
| Two clear crosswalk rows | Complete import; bounded investigation is clear | Verify the pack, then import its artifact index into PEG |
| One AFS identity maps to two MDG identities | Complete import; one cardinality finding | Preserve the producer-owned finding as a PEG defect, not an implicit resolution |
| A byte changes in a copied handoff | Pack verification fails | Stop before calling PEG |
| Valid XLSX followed by duplicate-cell refresh | Import exits 2; old graph bytes survive | Stop before building a handoff or calling PEG |

The two CSV cases each produce ten accepted **source-declaration/record pairs**:
two physical data rows interpreted by three node and two relationship declarations.
That is not ten unique source rows or ten newly created objects. The successful
clear focus retains three objects and two observed relationships; the cardinality
case retains five objects, four relationships and one externally owned finding.

`commands.json` retains actual subprocess exits and output. `result.json` separates
import completeness, native investigation status, byte verification, received
findings and PEG policy status. Source-row provenance and the authored observation
time are checked through the artifact-index import.

## Read the result as a consultant, not as a traffic light

Both graph-only PEG reviews can say `PASS`: the graph is structurally valid and no
optional assurance policy is enabled. Neither graph contains project requirements,
so requirement coverage is displayed as **n/a**, not proof of project acceptance.
The cardinality example still has a failed producer policy and a defect. The next
human decision is whether the supplied identity policy matches the actual business
grain, which export proves the intended link, and whether a project-owned bridge
or correction is needed. The tools do not choose a winning customer identity.

The observation time is fixed synthetic fixture data, not a new live observation.
The import report remains a separate sidecar; it is not inside the handoff manifest
and is not authenticated by pack verification. An aborted import's previously
accepted records remain provisional. The saved old graph is not revalidated by
that failure and is not exported by this rehearsal.

This is a serial local demonstration, not a transactional import service or a
concurrency-safe orchestration framework. Files must not change between verification
and consumption; hashes establish retained-byte consistency, not authenticity,
completeness, freshness, business acceptance, migration or replay permission.
Real practitioner usefulness and end-to-end consulting time remain unmeasured.
