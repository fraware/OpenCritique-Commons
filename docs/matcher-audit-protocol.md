# Matcher-audit pilot protocol

Issue #6. Protocol id: `matcher-audit-pilot-v0.1`.

## Population

All matcher decisions from a frozen evaluation result over the active benchmark
case set. The current pilot denominator is the **maintainer-owned sample corpus**
(`corpus/samples/` and derived adapter fixtures). Pilots on samples **do not**
authorize scientific performance claims and are not a substitute for a natural
adjudicated set (tracked on issue #6). Measured denominators are archived in
[matcher-audit-denominators.md](matcher-audit-denominators.md).

## Claim boundary

| Claim | Status |
|---|---|
| Sample matcher-audit protocol executable end-to-end | In scope |
| Sample decision volume sufficient for tooling gates | In scope (report denominator explicitly) |
| Natural / PeerQA matcher-audit ≥100 decisions | Blocked — issue #6 |
| Performance / comparative reviewer claims | Forbidden |

## Strata

- Accepted matches near threshold (`|score - threshold| ≤ 0.1`)
- Accepted matches far from threshold
- Unmatched submissions
- Unmatched references
- Ambiguous anchors
- Concern-type disagreements
- Severity disagreements
- Each domain profile (at least one representative)

## Sample size and seed

- Target: 100 match decisions, or every available decision when fewer exist
- Random seed is versioned with the sample (`MatcherAuditSample.random_seed`)
- Reports must state the actual denominator and that it is sample-only

## Blinding

Auditors see concern text and anchors only. System identity and leaderboard
consequences are withheld. Studio mode: `/studio` matcher-audit panel consumes
`blinded_payload` only.

## Decisions

- `correct_match`
- `partial_overbroad_match` (must not collapse into correct)
- `incorrect_match`
- `unresolved`

## Adjudication

Two primaries; disagreements route to tie-break. Model judgments may propose
candidates but **must not** determine gold outcomes.

## Analysis and gates

Report raw agreement, chance-corrected agreement (Cohen's κ), disagreement
categories, and estimated false-match / missed-match rates with an explicit
uncertainty note.

**Human audits may invalidate a matching policy.** If estimated false-match rate
exceeds the configured gate, `configuration_gate` fails and scorecards must
disclose that the matcher audit gate did not pass.

## Implementation

- Module: `opencritique_evaluation.matcher_audit`
- API: `GET/POST /expert/matcher-audit/...` (blinded payloads)
- Docs+API fallback when studio is unavailable
- Pilot fixtures: sample evaluations derived from `corpus/samples/`

Private rights-owned pilots (method tooling, not natural DoD):
[private-evaluation-pilot.md](private-evaluation-pilot.md).

## Holdout custody definition of done (scientific gate #7)

Protocol documentation and ledger ``IMPORTED`` counts are **not** sufficient.

Scientific holdout custody requires:

| Artifact | Requirement |
|---|---|
| `HoldoutSetManifest` | Frozen case IDs + content hashes; freeze time; custodian; developer-exclusion list; opaque private locator (`urn:` / `vault:` / `enc:` / `opaque:` — no plaintext manuscript paths); refresh/retirement policy; contamination declaration fields |
| Append-only access log | Actor, action, timestamp, purpose per entry; contiguous sequence from 0 |
| `HoldoutCustodyAttestation` | Signed `SignedEvidenceEnvelope` over `holdout_manifest_hash` + `access_log_head_hash` (mirrored in `subject_hashes`), freeze binding, custodian, opaque locator |
| Attested natural case count | ≥40 cases **inside the attested holdout set** |

Evidence path: `governance/evidence/attestations/holdout-custody.envelope.json`.
Machine check: `scripts/check_v09_scientific_gates.py` gate `holdout_custody`.
Until a verified envelope exists, the gate stays **NO-GO** with `missing_attestation`.
