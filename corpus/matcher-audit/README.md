# Matcher-audit evidence (issue #6)

Natural session manifests for denominator discovery by
`scripts/check_v09_gates.py` / `discover_natural_decision_count`.

## Layout

```text
corpus/matcher-audit/
  README.md
  sessions/          # MatcherAuditSessionManifest JSON (natural only for DoD)
```

## Rules

- Place only real audit session manifests here after natural populations exist.
- Sample evidence class sessions do **not** satisfy the natural DoD.
- Do **not** fabricate natural decision counts or set
  `performance_claims_authorized=true`.
- Empty `sessions/` is the correct state until rights-cleared natural audits run.

See [docs/matcher-audit-denominators.md](../docs/matcher-audit-denominators.md).
