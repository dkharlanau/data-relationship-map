# Stop on an invalid relationship policy

A migration analyst supplies a rule saying that one legacy customer may map to
at most one MDG business partner. If `max_outgoing` is misspelled, an ignored
rule must not turn an ambiguous crosswalk into a clean-looking review.

The policy loader and evaluator now reject invalid configuration before any
investigation, artifact index or handoff is written. This is input validation,
not a new cardinality rule or a claim that the supplied rules are sufficient.

## Explicit contract

The root must be an object containing only these optional fields:

- `relationship_rules`: an object keyed by exact, nonblank relationship types.
  Each rule is an object containing only `max_outgoing` and/or `max_incoming`.
- `report_identity_collisions`: a JSON boolean, default `true`.
- `fail_on_identity_collisions`: a JSON boolean, default `true`.

A limit must be a nonnegative JSON integer. Zero prohibits observed edges in
that direction. Omitted or `null` limits remain unrestricted. Strings such as
`"1"`, floats such as `1.0` or `1.9`, negative values and booleans are errors;
they are not converted into limits. Unknown fields are errors, not extensions.
Move descriptive annotations outside the executable policy.

JSON must have unique member names at every level, including escaped spellings.
Non-finite constants and numeric overflow, invalid UTF-8, unreadable files and
malformed JSON are rejected. Errors identify the fixed configuration category,
not the supplied values, field names or file contents.

### Compatibility is deliberate

A missing `relationship_rules` field, an empty object or a rule with no limits
still supplies no cardinality restriction. An empty policy still uses the
existing collision defaults. Exact relationship names are not normalized:
`mapped_to` and ` mapped_to ` are different names. No check establishes that a
rule name actually occurs in a particular extract.

Collision flags retain their previous interaction: if reporting is disabled,
collisions are not collected and therefore cannot fail that policy evaluation.
Use `report_identity_collisions: true` for both blocking and report-only collision
review; choose `fail_on_identity_collisions` explicitly. This change does not
redesign collision semantics, severity, review lifecycle or business approval.

Previously accepted malformed configuration (coercible limits, unknown fields,
wrong container types or repeated JSON members) must be corrected. Results and
handoff bytes for valid policies retain their existing meaning and format.

## Try a synthetic refusal and a valid finding

```bash
# Typo in a supplied limit: exits 2, prints no result JSON.
data-relationship-map policy examples/ambiguous-identity.json \
  examples/policy-contract/misspelled-limit.json

# Explicit 1:1 rules: exits 1, with cardinality findings, not a config error.
data-relationship-map policy examples/ambiguous-identity.json \
  examples/identity-policy.json
```

The same stop applies to `investigate`, `artifacts` and `handoff build`, including
their Python module commands. For invalid policy, output files and existing
handoff members are left untouched; no new output directory is created. An old
result left on disk is **not** a result of the failed command. Always check the
exit code before passing evidence to another tool.

Exit 2 denotes invalid configuration. Valid policy evaluation still returns
0 for no configured failures or 1 for configured failures. Other commands keep
their own existing status/exit contracts: for example, a structurally valid
handoff may retain policy findings. Handoff verification is integrity checking,
not policy replay, source authenticity or permission to migrate data.

These are synthetic regression examples. They involve no SAP connection,
client exports, automatic identity inference or practitioner acceptance.
