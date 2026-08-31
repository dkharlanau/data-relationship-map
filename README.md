# Data Relationship Map

**Cross-system identity and lineage investigations from ordinary CSV/XLSX enterprise exports.**

Data Relationship Map turns implicit relationships between legacy IDs, business partners, customers, suppliers, organizational assignments and other business objects into a deterministic graph with source-row provenance.

It is designed for the practical investigation question:

> **How is this object connected across systems, where did the relationship come from, what is ambiguous or broken, what can it affect downstream, and when was that relationship state actually observed?**

## Try it

Requires Python 3.10+.

```bash
python -m pip install .

data-relationship-map validate examples/customer-chain.json
data-relationship-map path examples/customer-chain.json AFS:4711 S4:10000891
data-relationship-map policy examples/customer-chain.json examples/identity-policy.json
```

The installed command is a thin dispatcher over the same deterministic modules used by CI. Existing `python relationship_*.py ...` workflows remain supported.

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

The handoff contains the bounded canonical graph, the same investigation as JSON, Markdown and standalone HTML, a bounded `artifact-index.json`, and a manifest with a deterministic `pack_id`, byte counts and SHA-256 hashes. Verification checks every retained file and recomputes semantic identity. Unrelated nodes and findings are excluded; invalid models and unknown focus objects fail before a pack is written. Version `0.2` packs add the artifact index, while the verifier continues to accept retained `0.1` packs.

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

## Build the graph from exports

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
