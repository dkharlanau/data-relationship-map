# Data Relationship Map

**Cross-system identity and lineage investigations from ordinary CSV/XLSX enterprise exports.**

Data Relationship Map turns implicit relationships between legacy IDs, business partners, customers, suppliers, organizational assignments and other business objects into a deterministic graph with source-row provenance.

It is designed for the practical investigation question:

> **How is this object connected across systems, where did the relationship come from, what is ambiguous or broken, and what can this object affect downstream?**

## Try it

Requires Python 3.10+.

```bash
python -m pip install .

data-relationship-map validate examples/customer-chain.json
data-relationship-map path examples/customer-chain.json AFS:4711 S4:10000891
data-relationship-map policy examples/customer-chain.json examples/identity-policy.json
```

The installed command is a thin dispatcher over the same deterministic modules used by CI. Existing `python relationship_*.py ...` workflows remain supported.

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

## Stable investigation artifacts

Objects, relationships and policy findings can be exposed through stable logical references:

```bash
data-relationship-map artifacts examples/customer-chain.json \
  --policy examples/identity-policy.json \
  --output build/relationship-artifacts.json
```

The artifact index uses producer-owned `eac://` identities and retains source provenance. These are logical references, not network URLs or trust assertions; downstream assurance tools must bind them explicitly.

This makes findings reusable without copying Data Relationship Map's semantic ownership into another repository.

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
- snapshot relationship/orphan drift;
- stable `eac://` references for objects, relationships and findings;
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

Data Relationship Map owns the **observed identity/relationship model and findings derived from supplied exports**. It does not become the authoring home for Mapping-as-Code transformation intent, Reconciliation-as-Code controls, or Enterprise Change Graph propagation rules.

The next product step is one consolidated investigation decision surface: structural findings + identity/cardinality policy + bounded lineage + exact source provenance in one reviewer-friendly report. See [ROADMAP.md](ROADMAP.md).

## Related projects

- [Mapping as Code](https://github.com/dkharlanau/mapping-as-code)
- [Reconciliation as Code](https://github.com/dkharlanau/reconciliation-as-code)
- [Transformation Graph](https://github.com/dkharlanau/transformation-graph)
- [Enterprise Change Graph](https://github.com/dkharlanau/enterprise-change-graph)
- [Project Evidence Graph](https://github.com/dkharlanau/project-evidence-graph)
- [Visual Workbench](https://github.com/dkharlanau/visual-workbench)

Portfolio map: https://dkharlanau.github.io/products/

## Status

**Executable MVP / active development.** Multi-source CSV/XLSX ingestion, explicit normalization, provenance, collision/cardinality diagnostics, identity paths, directional lineage, stable artifact references, snapshot drift, installed CLI, tests and CI are implemented.
