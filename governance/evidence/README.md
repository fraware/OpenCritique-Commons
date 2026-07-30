# Authenticity evidence artifacts

Machine-checkable inputs for `scripts/check_v09_scientific_gates.py`
(engineering scaffolding is checked separately by
`scripts/check_v09_engineering_gates.py`). Scientific gates **fail closed**
when these artifacts are absent, blocked, or incomplete. Do **not** fabricate
production exports, natural manuscripts, adjudicator IDs, or natural session
counts to flip a gate.

`performance_claims_authorized` must remain **false** in every artifact.

## Layout

| Artifact | Path | Gate |
|---|---|---|
| Acquisition ledger (natural imports) | `corpus/acquisition-ledger.json` | scientific #1 / #7 |
| Production Coarse MANIFEST | `fixtures/coarse/production/MANIFEST.json` | scientific #2 |
| Production OpenReviewer MANIFEST | `fixtures/openreviewer/production/MANIFEST.json` | scientific #3 |
| Production signing trust store | `trust/scorecard-trust-store.json` | scientific #4 |
| Two-domain staffing roster | `governance/evidence/natural-adjudication-staffing.json` | scientific #5 |
| Natural matcher-audit sessions | `corpus/matcher-audit/sessions/*.json` | scientific #6 |
| Expert-natural independent benchmarks | `benchmarks/*/manifest.json` | scientific #8 |

## Staffing roster

Schema: [natural-adjudication-staffing.schema.json](natural-adjudication-staffing.schema.json).

`status=ready` requires ≥2 domain profiles, each with ≥2 independent adjudicator
IDs. Until then keep `status=blocked` with an honest `blocked_reason`.

## Matcher-audit sessions

Drop natural `MatcherAuditSessionManifest` JSON files under
`corpus/matcher-audit/sessions/`. Sample sessions do **not** count toward the
≥100 natural decision DoD. See [../docs/matcher-audit-denominators.md](../docs/matcher-audit-denominators.md).
