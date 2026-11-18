# A ship-to connection is not an identity match

A consultant receives a customer crosswalk and a partner-assignment export.
The legacy customer points to one MDG business partner. That partner has two
ship-to partners in sales area 1000 / 10 / 00. All four records are connected,
but the two ship-to partners are not asserted to be the same object as the
sold-to partner.

This synthetic example makes that distinction executable. It uses invented IDs,
ordinary CSV columns and project-defined relationship names, not SAP table
joins or a live-system extract. The source observation time is unknown; do not
substitute the time you ran these commands.

## Import the two different kinds of evidence

From the repository root, after installing the package:

```bash
data-relationship-map import-csv examples/bp-connection-paths/manifest.json \
  --output /tmp/bp-connections.json --import-report /tmp/bp-import-report.json
data-relationship-map validate /tmp/bp-connections.json
data-relationship-map policy /tmp/bp-connections.json examples/bp-connection-paths/policy.json
```

The import accounts for seven source-declaration rows: four objects, one
crosswalk and two partner assignments, all accepted. IDs include the supplied
system and client. The partner relationship name includes the supplied sales
organization, distribution channel and division, so this example does not flatten
those assignments into an unscoped ship-to edge. This is an explicit fixture
choice, not a universal representation of SAP organizational data.

The graph is structurally valid. The supplied 1:1 rule covers only
'explicit_crosswalk'. It deliberately imposes no 1:1 rule on the two partner
assignments. Policy PASS means those supplied checks passed, not that the
relationship interpretation has been approved.

## Ask two different questions

“Is there any connection through these supplied relationships?”

```bash
data-relationship-map path /tmp/bp-connections.json \
  LEGACY:100:0004711 S4:100:0008001
```

Result, exit 0:

```text
LEGACY:100:0004711 -> MDG:100:0009001 -> S4:100:0008001
```

“Does the supplied crosswalk alone connect those two IDs?”

```bash
data-relationship-map path /tmp/bp-connections.json \
  LEGACY:100:0004711 S4:100:0008001 --relation explicit_crosswalk
```

Result: NO_PATH, exit 2. The tool refuses to use the partner assignment to
complete that selected path. This does **not** prove the records are unrelated;
it reports no connection under the selected types in this supplied snapshot.
A misspelled or absent type also returns no path. Inspect the exact type names
rather than silently broadening the search.

The explicit crosswalk itself remains traversable:

```bash
data-relationship-map path /tmp/bp-connections.json \
  LEGACY:100:0004711 MDG:100:0009001 --relation explicit_crosswalk
```

To include both kinds of relationship deliberately, repeat the option:

```bash
data-relationship-map path /tmp/bp-connections.json \
  LEGACY:100:0004711 S4:100:0008001 \
  --relation explicit_crosswalk --relation ship_to_in_sales_area:1000:10:00
```

Options are alternatives, not a required sequence. Matching is exact and
case-sensitive; blank names or surrounding whitespace are rejected. No filter
keeps the previous all-types behavior. Paths remain **undirected connections**;
use lineage for directional traversal. A zero-edge path from a known ID to
itself makes no cross-system identity claim.

## Retain the context for a reviewer

```bash
data-relationship-map handoff build /tmp/bp-connections.json /tmp/bp-connections-pack \
  --focus LEGACY:100:0004711 --max-depth 2 \
  --policy examples/bp-connection-paths/policy.json
data-relationship-map handoff verify /tmp/bp-connections-pack
```

The path filter does **not** change the investigation, lineage, policy or handoff
scope. This bounded pack intentionally retains both crosswalk and partner
relationships. Its graph records crosswalk.csv row 2 and partners.csv rows
2–3; follow those source locations before deciding what the connection means.
The terminal path itself lists IDs, not edge-level proof. No observation time
was supplied, so the artifact index retains unknown time.

The pack verifier checks retained integrity. Neither its success nor a found
path establishes source authority, freshness, cardinality compliance, identity,
or business approval. A crosswalk type is a supplied claim, not certification.
Ask the responsible data owner whether the columns, organizational scope and
crosswalk semantics are appropriate before using the IDs as reconciliation keys.

This advances the synthetic starter in issues #6/#7. It does not replace the
remaining scenarios or the three independent SAP/data practitioner reviews.
