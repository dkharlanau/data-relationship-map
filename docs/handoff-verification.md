# Verify the package before using the relationship evidence

A consultant receives a bounded customer-to-business-partner crosswalk. Before
passing its artifact index to another tool, they need to know whether the expected
files are present and still match the retained package. A parser crash is not an
answer, and a symbolic link to a different file is not a self-contained handoff.

```bash
data-relationship-map handoff build examples/customer-chain.json \
  build/customer-handoff --focus AFS:4711 --max-depth 2 \
  --policy examples/identity-policy.json --observed-at 2026-08-25T10:00:00Z
data-relationship-map handoff verify build/customer-handoff
```

The example and observation time are synthetic. `verify` returns JSON and exits
with **0 for valid** or **1 for invalid**. An invalid result is a stop condition:
do not import its artifact index into Project Evidence Graph. CLI usage errors
remain separate. The executable [handoff rehearsal](project-evidence-rehearsal.md)
shows this stop condition alongside a failed import that leaves an older graph
on disk.

## What is checked

- The manifest must be an unambiguous UTF-8 JSON object. Repeated member names,
  including escaped spellings, and non-finite numbers are rejected. The same JSON
  rules apply to the graph, investigation and, in format 0.2, artifact index.
- Only format `0.1` and `0.2` are accepted. An absent version retains the original
  0.1 interpretation; a numeric `0.2` is not silently converted into a string.
- The manifest must declare exactly the required filenames for that format, each
  with a lowercase SHA-256 digest and a non-negative integer byte count. Booleans
  are not byte counts. Unknown manifest paths are rejected, not followed.
- The manifest and required members must be direct regular files, not symbolic
  links, directories or pipes. Filesystem read errors return an invalid result.
- Each required member is read once. Its hash, byte count and the semantic pack
  ID use those captured bytes, rather than separately reopening the file.
- Failure output uses fixed error categories and known filenames, without
  echoing input values, unknown keys or filesystem exception paths.

Retained 0.1 packages continue to use their four-file identity. Format 0.2 adds
`artifact-index.json`. Existing producer output remains compatible. Unlisted
sidecar files in the directory are neither covered nor consumed by verification.
Nonstandard manifests previously tolerated through permissive parsing can now
fail; regenerate them from the intended source rather than weakening validation.

## What a valid result does not mean

This is **byte and semantic-ID consistency**, not a signature or proof of who
created the evidence. Someone able to rewrite all files and the manifest can
produce a different internally consistent package. Manifest status, bounds and
summary metadata are not independently replayed against the graph. The verifier
does not rerun identity/cardinality policy or decide whether the observed link is
correct, current, authorized or accepted by a practitioner.

Do not use this check as an adversarial filesystem sandbox: it does not lock a
directory, prevent concurrent replacement between inspection and read, reject
hard links, validate every ancestor directory, or impose resource-size limits.
Use a trusted, stable local directory. The later consumer reads a path separately;
do not change that directory between verification and import.

Finally, a graph-only PEG `PASS` can coexist with a native identity finding and
zero requirements. Keep the finding visible and obtain the project-owned bridge
and human decision. Verification does not approve a migration or resolve a
customer identity.
