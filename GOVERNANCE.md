# Governance requirements

OpenCritique Commons is governed around scientific inspectability, expert independence, and separation of powers.

## Constitutional requirements

1. **Concern-centered design.** Concerns about manuscript claims are the primary scientific objects.
2. **Evidence visibility.** Major and critical concerns expose supporting evidence.
3. **Defense requirement.** Major and critical concerns document the strongest plausible manuscript defense before final confirmation.
4. **Severity asymmetry.** False critical allegations receive substantially greater scrutiny and penalty than missed minor observations.
5. **Evaluation independence.** Private holdouts and final adjudication are controlled separately from evaluated-system development.
6. **Privacy by default.** Retention, benchmark use, model training, public release, and expert redistribution require separate authorization.
7. **No automated publication judgment.** The public core does not issue universal accept or reject decisions.
8. **Negative-result publication.** Evaluation procedures permit regressions and poor performance to be reported.
9. **Versioned truth.** Scientific records are corrected through new events and versions, not silent overwrites.
10. **Inspectability.** Published scores identify the case set, scoring policy, system version, run manifest, and adjudication basis.

## Human-evaluation separation

The following responsibilities must be assigned and logged separately where staffing permits:

- reviewer-system development;
- natural-case rights review;
- claim reconstruction;
- concern construction;
- calibration-reference construction;
- primary adjudication;
- tie-break adjudication;
- private-holdout custody;
- final score publication;
- security administration;
- compensation approval and payment.

The author of a calibration reference should not be the sole authority approving that reference. Stable calibration gold labels require at least two independent adjudications agreeing on validity and severity.

One person may temporarily occupy several roles during alpha development, but overlaps must be disclosed and cannot support claims of independent comparative evaluation.

## Expert qualification

Qualification is specific to a domain profile. Calibration results authorize task eligibility; they do not constitute a public rank or general measure of scientific ability. Qualification thresholds, false-critical ceilings, expiry rules, and revocation must be versioned.

Experts must disclose conflicts before each task. Sponsors, system developers, case authors, and project leadership may not direct an expert toward a desired scientific outcome.

## Data-use decisions

Rights classification and allowed use are distinct. A public document does not automatically authorize expert redistribution, benchmark inclusion, dataset release, or model training. Every use grant must identify authority, basis, scope, grantor, and expiry or revocation where applicable.

Contributor attestation establishes a declared basis for processing; it does not transfer ownership or replace legal review.

## Compensation and attribution

Scientific expert labor should be compensated under a transparent schedule when funding permits. Payment must be tied to task completion, never to a particular decision. Public attribution is opt-in and independent from payment. Compensation records are private.

## Changes

Changes to constitutional requirements, calibration scoring, blinding rules, severity policy, qualification gates, or public-core licensing require a public decision record under `governance/decisions/`. Historical records are superseded, not edited after acceptance.
