# Authenticity evidence artifacts

Machine-checkable inputs for `scripts/check_v09_scientific_gates.py`
(engineering scaffolding is checked separately by
`scripts/check_v09_engineering_gates.py`). Scientific gates **fail closed**
when signed evidence attestations are absent, blocked, or fail verification.
Do **not** fabricate production exports, natural manuscripts, adjudicator IDs,
or natural session counts to flip a gate.

`performance_claims_authorized` must remain **false** in every artifact.

## Attestation-first scientific gates (PR 42)

Blocking scientific gates verify `SignedEvidenceEnvelope` files under
[`attestations/`](attestations/). Expected paths and blocked placeholders are
documented there. Failure reasons include `missing_attestation`,
`signature_invalid` / `signature_tamper`, binding mismatches, expiry, and
revocation — never a false green from Boolean JSON alone.

## Supporting artifacts (binding subjects)

| Artifact | Path | Bound by |
|---|---|---|
| Acquisition ledger (natural imports) | `corpus/acquisition-ledger.json` | `natural_corpus` (informational for holdout; not the gate #7 denominator) |
| Holdout set manifest + access log | private custody store (opaque locator only in-repo) | `holdout_custody` (attested set ≥40 cases + freeze/log-head binding) |
| Production Coarse MANIFEST | `fixtures/coarse/production/MANIFEST.json` | `reviewer_export_authenticity` (coarse) |
| Production OpenReviewer MANIFEST | `fixtures/openreviewer/production/MANIFEST.json` | `reviewer_export_authenticity` (openreviewer) |
| Production signing trust store | `trust/scorecard-trust-store.json` | scientific #4 (public keys) + attestation verify |
| Two-domain staffing roster | `governance/evidence/natural-adjudication-staffing.json` | `expert_staffing` |
| Natural matcher-audit sessions | `corpus/matcher-audit/sessions/*.json` + `*.agreement.json` | `matcher_audit_completion` (completed dual-judgment count) |
| Expert-natural independent benchmarks | `benchmarks/*/manifest.json` | `independent_evaluation` |

## Staffing roster

Schema: [natural-adjudication-staffing.schema.json](natural-adjudication-staffing.schema.json).

`status=ready` requires ≥2 domain profiles, each with ≥2 independent adjudicator
IDs. Until then keep `status=blocked` with an honest `blocked_reason`. Roster
readiness alone does **not** pass scientific gate #5 without a verified
`expert-staffing.envelope.json`.

## Matcher-audit sessions

Drop natural `MatcherAuditSessionManifest` JSON files under
`corpus/matcher-audit/sessions/` with companion `*.agreement.json` reports.
Sample sessions do **not** count toward the ≥100 natural decision DoD. See
[../docs/matcher-audit-denominators.md](../docs/matcher-audit-denominators.md).
Session `sampled_count` alone does **not** pass scientific gate #6 — completed
dual-primary (+ tie-break) adjudication and a verified
`matcher-audit-completion.envelope.json` are required.
