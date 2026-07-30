# Signed scientific evidence attestations

Scientific gates in `scripts/check_v09_scientific_gates.py` require a
cryptographically verified `SignedEvidenceEnvelope` for each blocking authenticity
check. Boolean JSON, roster status flags, ledger counts, and production MANIFEST
presence alone are **not** sufficient.

Until real evidence is issued, envelopes are **absent**. Gates stay **NO-GO** with
explicit `missing_attestation` (or `signature_invalid` / binding failures when a
forged envelope is present). Placeholders below document required fields only —
they are intentionally **not** valid signed envelopes.

`performance_claims_authorized` must remain **false** everywhere.

## Expected envelope paths

| Attestation | Envelope path | Gate |
|---|---|---|
| Natural corpus | `natural-corpus.envelope.json` | scientific #1 |
| Reviewer export (Coarse) | `reviewer-export-coarse.envelope.json` | scientific #2 |
| Reviewer export (OpenReviewer) | `reviewer-export-openreviewer.envelope.json` | scientific #3 |
| Expert staffing | `expert-staffing.envelope.json` | scientific #5 |
| Matcher-audit completion | `matcher-audit-completion.envelope.json` | scientific #6 |
| Holdout custody | `holdout-custody.envelope.json` | scientific #7 |
| Independent evaluation | `independent-evaluation.envelope.json` | scientific #8 |

Signing role: trust-store `evidence_authority` (or `offline_root`). Test keys are
rejected under production verification policy.

## Placeholders

`*.placeholder.json` files describe required attestation payload fields and stay
`verification_status=blocked`. Do not rename them to `*.envelope.json` without a
real Ed25519 signature over the canonical attestation bytes.
