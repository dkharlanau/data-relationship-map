# Review a business-partner mapping before comparing values

A reconciliation can compare the wrong records perfectly. Before comparing
balances or migrating attributes, an analyst needs to know what the supplied
customer and business-partner links actually say, where the links came from,
and where the evidence is incomplete.

This starter runs one small, synthetic investigation through the existing DRM
commands. It reuses the ordinary export rows in
[the connection-path example](../examples/bp-connection-paths/) and creates
deliberate variations in a new output directory. It needs no SAP connection,
client data, paid service or additional runtime dependency.

## Run it from a source checkout

After installing DRM into your own virtual environment, point the runner at
that environment's trusted executable. Use a new output directory:

```bash
python -m venv .venv
.venv/bin/python -m pip install .
python scripts/rehearse_bp_starter.py \
  --drm-cli "$PWD/.venv/bin/data-relationship-map" \
  --output /tmp/bp-starter-review
```

The source checkout is required: the runner and example CSVs are not an installed
package command. Installation may need your normal approved Python package
source. The rehearsal itself uses only local files and the explicit executable.
Do not point it at an executable or project supplied by an untrusted party.

On success, open REVIEW.md for the case table and result.json for the checked
results. commands.json records all 43 DRM invocations, including expected
nonzero exits. Each case retains its generated CSVs or XLSX workbooks, manifest, import accounting,
graph, investigation JSON/Markdown/HTML and, where allowed, an integrity-verifiable
handoff. No existing output directory is overwritten or cleared.

## Read the outcomes, not just the exit code

| Case | Expected observation | Decision still belonging to the reviewer |
| --- | --- | --- |
| Clear crosswalk | One legacy ID maps to one MDG ID; supplied checks are clear | Is this crosswalk authoritative and appropriate for the intended comparison? |
| Unexpected 1:N | One legacy ID has two supplied targets; one cardinality finding | Which target is intended, or should the explicit policy change? |
| Broken reference | A target ID has no supplied object; investigation is invalid and handoff stops | Obtain the missing export row or correct the link. |
| Orphan | An additional target is unlinked; full investigation reports findings | Investigate it separately. The focused pack excludes it and can be clear. |
| Conflicting metadata | Two labels are supplied for one exact ID | Review both descriptions and contributing node rows, without an automatic winner. |
| Changed crosswalk | The second snapshot maps to a different target; both snapshots can be individually clear | Was the change intended, and which source should govern the next action? |
| Separate client namespaces | The same display IDs in clients 100 and 200 produce distinct objects and links | Does the supplied key include every namespace needed for this project? |
| Valid partner assignment | Two ship-to partners connect to one sold-to partner in a supplied sales area | Do not confuse partner relationships with identity links. |
| Aborted refresh | A required ID component is blank; the old graph remains unchanged | Stop. The old graph has not been revalidated against the failed new export. |

The eight graph snapshots include the five synthetic scenarios requested in
issue #6; the aborted refresh is a separate failure-path check. The broader
export-shape backlog in #7 is not automatically closed by this run.

The graph IDs retain the supplied system and client. Partner relationship types
retain the fixture's sales organization, distribution channel and division.
These are explicit example choices, not undocumented SAP table joins or a
universal interpretation of organizational data.

A deliberately selected crosswalk-only path to the ship-to record returns
NO_PATH. The unrestricted connection still exists. The tool refuses the inference,
not the possibility that further evidence could establish another relationship.

## Rehearse XLSX without losing string identity

The same runner can generate and import workbooks instead of CSVs:

```bash
python scripts/rehearse_bp_starter.py \
  --drm-cli "$PWD/.venv/bin/data-relationship-map" \
  --format xlsx --output /tmp/bp-starter-xlsx-review
```

The synthetic workbook writer uses inline strings for every cell. Values such
as 0004711 and 0 stay strings; formula-looking text is not written as a formula.
This is not a qualification of arbitrary Excel formulas, cached values, date
formats, locales or formatting, and it cannot restore identifiers that a source
application has already rounded or stripped.

CSV and XLSX produce the same business fields and native case statuses. Their
provenance differs: file and row versus file, sheet and row. Their handoff pack
IDs consequently differ. Verify each pack separately; a CSV integrity result
does not verify the XLSX artifact. The source checkout supplies the example
writer, not a new installed runtime dependency.

The separate-client case uses the same legacy and MDG numbers in clients 100
and 200. The example ID template includes the client, so both pairs survive and
the focused client-100 pack excludes the disconnected client-200 component.
This tests the supplied template, not automatic detection of an omitted business
key: required columns establish completeness, not that every column is used in
the ID template. A project owner must decide which fields define identity.

No normalizers are injected. The existing opt-in XLSX normalization feature is
separate from this rehearsal. A raw-identity collision is evidence to review,
not proof that two source values represent the same business object.

## Compare the two observations

The clear and changed crosswalk cases use authored fixture timestamps:

- before: 2026-08-25T10:00:00Z;
- after: 2026-08-26T10:00:00Z.

These are retained in the respective handoff artifact indexes. They are not
live observations, export freshness checks or the measured time of a change.
The runner calls the existing diff command and saves snapshot-diff.json.
It checks that the old explicit_crosswalk edge was removed and the new one added.

Inspect row 2 in the two generated crosswalk.csv files, or the crosswalk
worksheets in XLSX mode, alongside the diff.
The diff describes differences between supplied graphs; it does not know why
the target changed, authorize that change or compare arbitrary source metadata.
A clear latest snapshot is not evidence that the transition was correct.

## Know the boundary of the handoff

The full investigation and the focused handoff can answer different questions.
In the orphan case, the unlinked target is visible in the full report but lies
outside the focus-connected pack. REVIEW.md shows both statuses so that a clear
subset does not erase the unresolved source finding.

The metadata-conflict case retains both descriptions and node-level contributing
rows. It does not attribute each value to an individual row or choose a winner.
The cardinality case retains a native finding. Pack verification checks retained
integrity, not business acceptance, authenticity or replay of every policy.

The import-report sidecar is retained next to the graph but remains outside the
verified handoff. A rejected refresh stops after import and does not validate or
re-export the surviving old graph. A failed or interrupted runner may retain
partial diagnostics; result.json is written only after all expected checks and
the reviewer table complete. This is a serial local rehearsal, not a transactional
production orchestrator or a defence against concurrent file changes.

This runner does not invoke Project Evidence Graph. The existing
[DRM → PEG rehearsal](project-evidence-rehearsal.md) owns that separate consumer
check. Do not transfer a previous consumer PASS to these new cases or treat
imported relationship evidence as satisfaction of a project requirement.

## Use the pack in a real review before claiming benefit

The next gate is three actual SAP/data practitioner reviews from issue #6.
Record which export columns each reviewer can obtain, how much preparation is
needed, what conclusion they reproduce, which wrong inference the pack prevents,
and what remains unresolved. Keep synthetic results separate from customer
work and do not collect sensitive extracts without the project's permission.

No practitioner review, productivity gain, production SAP result or business
sign-off is established by the automated run.
