# Data Relationship Map

**Cross-system identity and lineage investigations from ordinary CSV/XLSX enterprise exports.**

Data Relationship Map turns implicit relationships between legacy IDs, business partners, customers, suppliers, organizational assignments and other business objects into a deterministic graph with source-row provenance.

It is designed for the practical investigation question:

> **How is this object connected across systems, where did the relationship come from, what is ambiguous or broken, what can it affect downstream, and when was that relationship state actually observed?**

XLSX imports reject ambiguous row/cell positions before constructing identities.
See the [synthetic coordinate examples](examples/xlsx-layout/README.md) and
[accounting limits](docs/import-accounting.md#xlsx-coordinate-integrity).

## Try it

Requires Python 3.10+.

```bash
python -m pip install .

data-relationship-map validate examples/customer-chain.json
data-relationship-map path examples/customer-chain.json AFS:4711 S4:10000891
data-relationship-map policy examples/customer-chain.json examples/identity-policy.json
```

The installed command is a thin dispatcher over the same deterministic modules used by CI. Existing `python relationship_*.py ...` workflows remain supported.

Supplied cardinality policies are validated before results are written: misspelled
fields, ambiguous JSON and non-integer limits stop with exit 2 rather than silently
weakening the checks. See the [policy contract and synthetic refusal](docs/policy-contract.md).

## Start with one investigation report

The primary review surface combines structural diagnostics, explicit identity/cardinality policy, bounded upstream/downstream lineage and source provenance:

```bash
data-relationship-map investigate examples/customer-chain.json \
  --policy examples/identity-policy.json \
  --focus AFS:4711 \
  --json-output build/investigation.json \
  --markdown build/investigation.md
```

The status is deterministic:

- `clear` — no structural or supplied-policy findings;
- `findings` — graph is usable but has investigation findings such as orphans or cardinality violations;
- `invalid_model` — structural contract is broken;
- `invalid_focus` — requested focus object does not exist.

The report does not infer relationships that are absent from the supplied model.

## Package a bounded handoff

An investigation can be reduced to the selected upstream/downstream context and retained as an integrity-checkable pack for another reviewer, tool or agent:

```bash
data-relationship-map handoff build examples/customer-chain.json \
  build/customer-handoff \
  --policy examples/identity-policy.json \
  --focus AFS:4711 \
  --max-depth 2 \
  --observed-at 2026-08-25T10:00:00Z

data-relationship-map handoff verify build/customer-handoff
```

The handoff contains the bounded canonical graph, the same investigation as JSON, Markdown and standalone HTML, a bounded `artifact-index.json`, and a manifest with a deterministic `pack_id`, byte counts and SHA-256 hashes. Verification checks the format's required files and recomputes semantic identity from the same captured bytes. It rejects malformed or ambiguous JSON, invalid manifest entries and direct symlink/non-regular members. Unrelated nodes and findings are excluded; invalid models and unknown focus objects fail before a pack is written. Version `0.2` packs add the artifact index, while the verifier continues to accept retained `0.1` packs. See [verification scope and stop conditions](docs/handoff-verification.md): integrity is not authorship, policy replay or business approval.

The [public synthetic handoff](https://dkharlanau.github.io/data-relationship-map/demo/handoff/investigation.html) can be reviewed in a browser. Its [manifest](https://dkharlanau.github.io/data-relationship-map/demo/handoff/manifest.json), [bounded graph](https://dkharlanau.github.io/data-relationship-map/demo/handoff/graph.json), and [artifact index](https://dkharlanau.github.io/data-relationship-map/demo/handoff/artifact-index.json) show the exact retained scope and machine handoff.

### Hand the bounded evidence to Project Evidence Graph

The retained artifact index is the implemented machine handoff. It is already inside the integrity-checked pack:

```bash
project-evidence-graph import-relationship \
  build/customer-handoff/artifact-index.json \
  --output build/project-relationship-evidence.json

project-evidence-graph analyze build/project-relationship-evidence.json
```

Project Evidence Graph preserves the producer observation time, represents observed objects and relationships as evidence, and represents failed relationship-policy findings as externally owned defects. It does not automatically attach them to a requirement or change; that bridge remains an explicit project-owned decision.

For an executable synthetic workflow with explicit stop conditions, see the
[DRM → PEG handoff rehearsal](docs/project-evidence-rehearsal.md). It separates
a successful import from a preserved old graph after failure, and retains native
findings even when a graph-only PEG review passes.

Run the two installed CLIs in separate virtual environments. Both MVP packages currently expose generic top-level Python module names, so a shared environment can create import-name collisions. The handoff is the verified JSON file contract between those environments; install order is not part of that contract.

## Build the graph from exports

Export headers must be non-empty and unique. CSV imports reject malformed quoting
and rows with too many or too few fields; use an explicit empty cell for a missing
value. XLSX imports reject populated cells beyond the header. These checks prevent
columns from silently disappearing before identity and lineage analysis. CSV row
provenance points to the physical starting line, including after multiline quoted
values or blank lines.

A non-empty source row must produce a non-empty node `id` or both relationship
endpoints (`from` and `to`). Otherwise the import stops with the file and source
row (also the worksheet for XLSX), exits with code 2, and leaves an existing
output file unchanged. Wholly blank rows are ignored. Remove intentionally
excluded records from the source export explicitly; a blank ID is not a filter.
Without an explicit component contract, this check validates the complete
rendered identity: `CUSTOMER:{ID}` can still render `CUSTOMER:` when `ID` is
blank. Declare the required source columns when a prefix is not a usable key.

To see the failure on synthetic data, run
`data-relationship-map import-csv examples/csv/missing-identity/manifest.json`.
It reports the missing node ID on line 3 rather than returning only the first
customer. Fill that ID in the source export before building a handoff.

### Protect the parts of a composite identity

An identifier such as `S4:100:` is not empty, but it may still be missing the
customer number your investigation needs. Tell the adapter which columns must
be present and non-blank on each populated row:

```json
{
  "file": "customers.csv",
  "id": "{SYSTEM}:{CLIENT}:{ID}",
  "system": "{SYSTEM}",
  "object": "customer",
  "required_identity_columns": ["SYSTEM", "CLIENT", "ID"]
}
```

Place this declaration on each applicable `node_sources` or
`relationship_sources` entry. For a relationship it can name columns used by
both `from` and `to`. The same declaration works for XLSX sources with a `sheet`.
It checks header presence even when there are no data rows, and checks values
after the existing XLSX normalizers. CSV header names remain exact; XLSX header
names retain the adapter's existing trimming behavior. A string, null, duplicate
name or blank name in place of a proper array is an error. An omitted declaration
or an empty array adds no component checks.

Run the synthetic example:

```bash
data-relationship-map import-csv examples/csv/composite-identity/valid.json \
  --output customer-model.json
data-relationship-map import-csv examples/csv/composite-identity/missing-id.json \
  --output customer-model.json
```

The first import retains `S4:100:0004711`, `S4:200:0004711`, and `S4:100:0`
as three distinct string IDs. The second exits 2 on line 3 because `ID` is
blank, before overwriting that output. Check the exit code: a retained file is
the previous result, not evidence that the failed import succeeded. Error text
identifies the file, row/sheet and column names, without echoing the row values.

This is an explicit input completeness check, not a SAP key definition, automatic
normalization, proof of identity, cardinality approval, or complete import-row
ledger. Choose columns from the agreed export contract. Wholly blank padding
remains ignored; optional fields can stay blank. Leading zeros and zero IDs stay
text unless an existing explicitly requested XLSX normalizer changes them.

CSV:

```bash
data-relationship-map import-csv examples/csv/manifest.json \
  --output customer-model.json

data-relationship-map validate customer-model.json
```

XLSX:

```bash
python examples/xlsx/make_sample.py examples/xlsx/customer_crosswalk.xlsx

data-relationship-map import-xlsx examples/xlsx/manifest.json \
  --output customer-xlsx-model.json
```

A manifest can combine several crosswalk, partner-function, organization or other extracts into one canonical investigation model while retaining file/sheet/row provenance.

## Ask different relationship questions explicitly

### Identity path

```bash
data-relationship-map path examples/customer-chain.json \
  AFS:4711 S4:10000891
```

`path` is intentionally symmetric. It answers **how are these two identities connected?** without pretending every relationship is directional impact.

### Downstream lineage

```bash
data-relationship-map lineage examples/customer-chain.json AFS:4711 \
  --direction downstream
```

### Upstream lineage

```bash
data-relationship-map lineage examples/customer-chain.json S4:10000891 \
  --direction upstream
```

### Bounded traversal

```bash
data-relationship-map lineage examples/customer-chain.json AFS:4711 \
  --direction downstream \
  --stop-system MDG
```

Lineage never silently walks an edge backwards. Output retains relationship type, provenance, deterministic paths, node depth and the boundary where traversal stopped.

## Detect identity and cardinality problems

A graph can be structurally valid and still be wrong for the business rule. A legacy customer may unexpectedly map to two target BPs, or several source IDs may converge where the relationship is expected to remain 1:1.

```json
{
  "relationship_rules": {
    "mapped_to": {"max_outgoing": 1, "max_incoming": 1},
    "replicated_to": {"max_outgoing": 1, "max_incoming": 1}
  },
  "report_identity_collisions": true,
  "fail_on_identity_collisions": true
}
```

```bash
data-relationship-map policy examples/customer-chain.json \
  examples/identity-policy.json
```

Policy output identifies the exact related IDs behind one-to-many or many-to-one ambiguity rather than reducing the problem to a generic validation error.

## Stable, freshness-aware investigation artifacts

Objects, relationships and policy findings can be exposed through stable logical references for downstream assurance:

```bash
data-relationship-map artifacts examples/customer-chain.json \
  --policy examples/identity-policy.json \
  --observed-at 2026-08-25T10:00:00Z \
  --output build/relationship-artifacts.json
```

`observed_at` is explicit and timezone-aware. The tool never substitutes the current wall-clock time. If the input model already contains `observed_at`, that value is used unless the CLI argument explicitly overrides it.

The artifact index uses producer-owned `eac://` identities and retains source provenance. These are logical references, not network URLs or trust assertions. Downstream tools must bind them explicitly.

Project Evidence Graph can import this index while preserving observation time. Use the standalone command when a full-model index is wanted outside a bounded pack:

```bash
project-evidence-graph import-relationship build/relationship-artifacts.json \
  --output build/project-relationship-evidence.json
```

A failed Data Relationship policy is not a broken import contract—the findings are the evidence. Missing observation time remains possible for backward compatibility, but a strict downstream freshness policy can and should reject undated evidence.

## Compare relationship state over time

```bash
data-relationship-map diff \
  examples/customer-chain.json \
  examples/customer-chain-after.json
```

The diff reports relationship and orphan drift so an investigation can distinguish a long-standing anomaly from a newly introduced relationship change.

## Current capabilities

- CSV and `.xlsx` ingestion through small manifests;
- multiple source files in one canonical investigation model;
- XLSX reading without an Excel runtime dependency;
- composite IDs built directly from source columns;
- explicit normalization: `strip`, `upper`, `lower`, `strip_leading_zeros`;
- vendor-neutral canonical graph;
- file/sheet/row provenance;
- normalized identity-collision diagnostics instead of silent merge;
- conflicting attribute detection for repeated canonical IDs;
- broken-reference, duplicate and orphan detection;
- explicit relationship-cardinality policy;
- one-to-many and many-to-one ambiguity diagnostics;
- symmetric shortest identity path;
- strict downstream and upstream lineage;
- system/object and max-depth traversal boundaries;
- consolidated JSON/Markdown investigation report;
- standalone dependency-free HTML investigation report;
- bounded integrity-checkable handoff packs with deterministic identity, per-file SHA-256, and a retained machine artifact index;
- snapshot relationship/orphan drift;
- stable `eac://` references for objects, relationships and findings;
- explicit timezone-aware observation time for exported assurance artifacts;
- tested Project Evidence Graph consumption contract;
- installable `data-relationship-map` command;
- unit tests and installed-CLI smoke tests in GitHub Actions.

## Composite keys and normalization

```json
{
  "file": "customers.xlsx",
  "sheet": "Customers",
  "id": "KNVP:{KUNNR}:{VKORG}:{VTWEG}:{SPART}:{PARVW}",
  "normalizers": {
    "KUNNR": ["strip", "strip_leading_zeros"],
    "PARVW": "upper"
  }
}
```

Normalization is explicit rather than automatic. If two raw identities normalize to the same canonical ID, the node records the collision plus source provenance so the merge can be investigated.

## Canonical model

```json
{
  "observed_at": "2026-08-25T10:00:00Z",
  "nodes": [
    {
      "id": "AFS:4711",
      "system": "AFS",
      "object": "customer",
      "provenance": [
        {"file": "customer_crosswalk.xlsx", "sheet": "Crosswalk", "row": 2}
      ]
    }
  ],
  "relationships": [
    {
      "from": "AFS:4711",
      "to": "MDG:7200311",
      "type": "mapped_to",
      "provenance": {
        "file": "customer_crosswalk.xlsx",
        "sheet": "Crosswalk",
        "row": 2
      }
    }
  ]
}
```

## Ownership boundary

Data Relationship Map owns the **observed identity/relationship model, observation time, and findings derived from supplied exports**. It does not become the authoring home for Mapping-as-Code transformation intent, Reconciliation-as-Code controls, Project Evidence Graph assurance relationships, or Enterprise Change Graph propagation rules.

The next product step is explicit finding severity and review lifecycle policy. See [ROADMAP.md](ROADMAP.md).

## Related projects

- [Project Evidence Graph](https://github.com/dkharlanau/project-evidence-graph) has an implemented `import-relationship` adapter for the retained artifact index; project attachment still requires an explicit bridge.
- [Transformation Graph](https://github.com/dkharlanau/transformation-graph) models governed transformation lineage. There is no direct adapter today, so observed identity links must not be presented as transformation intent.
- [Enterprise Change Graph](https://github.com/dkharlanau/enterprise-change-graph) models dependency and regression impact. There is no direct adapter today; bounded directional lineage is an input candidate, not an implemented handoff.
- [Reconciliation as Code](https://github.com/dkharlanau/reconciliation-as-code) evaluates explicit data controls. It does not currently consume Data Relationship Map artifacts directly.

Portfolio map: https://dkharlanau.github.io/products/

## Status

**Executable MVP / active development, v0.2.0.** Multi-source CSV/XLSX ingestion, explicit normalization, provenance, collision/cardinality diagnostics, identity paths, directional lineage, browser-ready investigation reports, bounded integrity-checkable handoffs with a Project Evidence Graph artifact index, freshness-aware stable artifacts, snapshot drift, installed CLI, tests and CI are implemented.

## About the author

Created and maintained by **Dzmitryi Kharlanau**, an SAP consultant and system analyst working across enterprise architecture, data, integration, operations, and practical AI.

- [Website and knowledge base](https://dkharlanau.github.io/)
- [LinkedIn](https://www.linkedin.com/in/dkharlanau/)

## Optional import accounting

Use `--import-report report.json` with `import-csv` or `import-xlsx` to retain per-source record dispositions alongside the unchanged canonical graph. Partial failure reports are explicitly incomplete and do not authorize using a retained old graph. See [the counting rules and synthetic example](docs/import-accounting.md).

## License notice

Use the repository’s [LICENSE](LICENSE) as the source of its license notice.
The package includes that file rather than assigning a different shorthand
license to the project. This metadata correction does not change the notice
or grant additional rights. Read the notice and the terms it references before
using or redistributing the project.
