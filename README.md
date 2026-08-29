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

Project Evidence Graph can import the index while preserving observation time:

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

The next product step is a bounded integrity-checkable handoff plus explicit finding lifecycle/severity policy. See [ROADMAP.md](ROADMAP.md).

## Related projects

- [Mapping as Code](https://github.com/dkharlanau/mapping-as-code)
- [Reconciliation as Code](https://github.com/dkharlanau/reconciliation-as-code)
- [Transformation Graph](https://github.com/dkharlanau/transformation-graph)
- [Enterprise Change Graph](https://github.com/dkharlanau/enterprise-change-graph)
- [Project Evidence Graph](https://github.com/dkharlanau/project-evidence-graph)
- [Visual Workbench](https://github.com/dkharlanau/visual-workbench)

Portfolio map: https://dkharlanau.github.io/products/

## Status

**Executable MVP / active development, v0.2.0.** Multi-source CSV/XLSX ingestion, explicit normalization, provenance, collision/cardinality diagnostics, identity paths, directional lineage, consolidated investigation reports, freshness-aware stable artifacts, snapshot drift, installed CLI, tests and CI are implemented.
