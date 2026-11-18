# Do not let an empty export hide a wrong normalization rule

An analyst may receive a header-only export today and actual rows tomorrow.
A typo in an explicitly configured ID transformation must not pass today simply
because there is no row on which to execute it. A JSON object is not an ordered
rule list: `{"upper": false}` must not secretly mean “apply upper”.

Generate the small synthetic fixture into a new directory, then use your trusted
installed DRM CLI:

```bash
python examples/xlsx-normalization/make_fixture.py /tmp/drm-normalizers-review
data-relationship-map import-xlsx /tmp/drm-normalizers-review/valid.json \
  --output /tmp/drm-normalizers-review/graph.json \
  --import-report /tmp/drm-normalizers-review/valid-report.json
```

The declared strip_leading_zeros rule intentionally merges supplied IDs 0004711
and 4711 into BP:4711. Inspect identity_collisions and the raw_identity and
normalization provenance. This is an observation of a configured transformation,
not proof of equivalence or a recommendation to normalize customer identifiers.

Now attempt a malformed rule against a header-only worksheet:

```bash
data-relationship-map import-xlsx /tmp/drm-normalizers-review/invalid-rule.json \
  --output /tmp/drm-normalizers-review/graph.json \
  --import-report /tmp/drm-normalizers-review/invalid-report.json
```

Expected: exit 2, an aborted report and the previous graph bytes unchanged. The
old graph is not revalidated. Repeat with missing-column.json: the declared
column does not exist in the header, so the empty export is not called complete.
A legitimate header-only export with valid rules and matching columns remains a
successful empty model; an entirely headerless worksheet cannot check declared
columns. No collect-all or general manifest-schema validation is claimed.

Accepted forms are exact strings or ordered lists of exact strings: strip,
upper, lower, strip_leading_zeros. Global rules run before source rules. An empty
source list is a no-op addition, not a reset of global rules. Unknown operations,
non-string rules, null/scalar collections and nested objects fail before workbook
reads. Field names are not silently trimmed or case-folded; worksheet headers
retain the adapter's existing trimming behavior.

CSV does not gain XLSX normalization through this change. No implicit rule,
fuzzy match, namespace discovery or business-key decision is added. The fixture
is synthetic; no SAP connection, customer acceptance or productivity result is
established. Import accounting remains outside the verified handoff.
