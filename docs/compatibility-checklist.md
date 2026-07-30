# OpenCritique-compatible interchange checklist

External tools and adapters may claim **OpenCritique-compatible** only for
**interchange**: producing or consuming frozen Commons schema types and, when
applicable, an adapter convert path. Compatibility is **not** endorsement of
reviewer quality, accuracy, or scientific performance.

Interchange identity is pinned by `SCHEMA_FREEZE_RELEASE=0.5.0a1`. Engineering
package versions (for example `0.6.0a0`) may advance without changing that freeze
identity. See [schema-compatibility.md](schema-compatibility.md).

## Hard invariants

- `performance_claims_authorized=false` (and any registry `claims` field) until
  §12 / v0.9 gates are met with real evidence.
- No fabricated production `MANIFEST.json` `status=ready`, fake hashed exports,
  or pretend upstream Git SHAs for sample fixtures.
- Private `runs/` never auto-promote into `fixtures/*/production/`.
- No leaderboard, ranking, or “best AI reviewer” language tied to Commons
  scorecards while claims remain locked.

## Checklist (interchange only)

Use this list before opening a community-adapters PR or stating compatibility in
external docs.

### Schemas

- [ ] Produce and/or consume frozen Commons types (`schema_id` /
      `schema_version` per [schema-compatibility.md](schema-compatibility.md)).
- [ ] Cite `SCHEMA_FREEZE_RELEASE=0.5.0a1` as the interchange freeze (not the
      package version alone).
- [ ] Fail closed on malformed input; do not silently reshape records to match
      one upstream tool.

### Adapter / export mapping

- [ ] Provide an adapter convert path **or** a documented export mapping into
      `EvaluationSubmission` / equivalent Commons types.
- [ ] Pin a **sample** adapter contract id for sample fixtures (for example
      `opencritique-sample-adapter-contract-v1`), not a pretend production Git
      SHA. Follow [adapter-authoring.md](adapter-authoring.md).
- [ ] Keep conversion-loss / field-fate reporting honest (preserved / normalized /
      omitted). Cross-adapter expectations:
      [cross-adapter-conformance.md](cross-adapter-conformance.md).

### Claims and marketing

- [ ] Keep all claims flags **false**.
- [ ] Scorecards and demos show **NOT AUTHORIZED** (or equivalent) for
      scientific performance.
- [ ] Do not imply production authenticity from sample or synthetic fixtures.

### Rights and redistribution

- [ ] Document rights posture for any fixtures you redistribute.
- [ ] Production trees use `fixtures/<slug>/production/MANIFEST.json` with
      fail-closed intake; leave `status` blocked/pending until genuine
      rights-cleared exports exist ([adapter-authenticity.md](adapter-authenticity.md)).

### Optional live runners

- [ ] Live invoke plugins write under private `runs/` only; refuse writes into
      `fixtures/*/production/` ([runner-plugins.md](runner-plugins.md)).

## Suggested machine-readable companion fields

When publishing an external compatibility statement (JSON or docs), include at
least:

| Field | Example / rule |
|---|---|
| `schema_freeze_release` | `"0.5.0a1"` |
| `performance_claims_authorized` | `false` |
| `interchange` | produce / consume / both |
| `adapter_convert_or_mapping` | path or URL to mapping docs |
| `sample_contract_id` | sample pin when applicable |
| `evidence_class` | `sample` \| `private_live` \| `production` |
| `rights_posture` | short statement for redistributed fixtures |

Community listing: [community-adapters.md](community-adapters.md) /
[`community-adapters.json`](community-adapters.json).

## Conformance helper

Before opening an adapter PR:

```bash
python scripts/check_adapter_compatibility.py path/to/adapter-or-fixtures
```

The script checks claims locks, sample contract presence, and refuses fake
production-ready pretenses. It emits short markdown suitable for a PR body.
It is **not** wired into default `scripts/check.sh`.

## Explicit non-claims

Meeting this checklist means:

- Your tool can exchange Commons-shaped records under the frozen schema, and/or
- Your adapter maps upstream exports without inventing severity, authenticity,
  or quality scores.

It does **not** mean OpenCritique Commons certifies your reviewer, unlocks §12
performance claims, or treats sample fixtures as production evidence.
