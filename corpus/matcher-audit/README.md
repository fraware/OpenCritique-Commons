# Matcher-audit evidence (issue #6)

Natural session manifests and agreement reports for completed-adjudication
discovery by `scripts/check_v09_scientific_gates.py` /
`discover_completed_matcher_audit` (also exposed as
`discover_natural_decision_count`).

## Layout

```text
corpus/matcher-audit/
  README.md
  sessions/                    # MatcherAuditSessionManifest JSON (natural for DoD)
    <stem>.json                # session manifest
    <stem>.agreement.json      # AuditAgreementReport (required to count)
```

## Rules

- Place only real audit session manifests here after natural populations exist.
- Sample evidence class sessions do **not** satisfy the natural DoD.
- `sampled_count` alone does **not** count; candidates need dual primary
  judgments (+ tie-break when required) in the companion agreement report.
- Do **not** fabricate natural decision counts or set
  `performance_claims_authorized=true`.
- Empty `sessions/` is the correct state until rights-cleared natural audits run.

Scientific gate #6 also requires a verified
`governance/evidence/attestations/matcher-audit-completion.envelope.json`.

See [docs/matcher-audit-denominators.md](../docs/matcher-audit-denominators.md).
