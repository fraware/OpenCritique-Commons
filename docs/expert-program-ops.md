# Expert program operations (issue #14)

Versioned operational policy for paid pilot readiness on **authorized** material
only (maintainer-owned samples until issue #7 clears natural imports).

Compensation, attribution, and qualification thresholds are **policy objects** —
not performance claims. `performance_claims_authorized` remains false.

## Related policy files

| Object | Path | Runtime loader |
|---|---|---|
| Compensation terms template | [expert-compensation-terms.md](expert-compensation-terms.md) + [../governance/policies/expert-compensation-terms.v0.1.json](../governance/policies/expert-compensation-terms.v0.1.json) | `load_compensation_policy` |
| Attribution opt-in | [expert-attribution-policy.md](expert-attribution-policy.md) + [../governance/policies/expert-attribution-policy.v0.1.json](../governance/policies/expert-attribution-policy.v0.1.json) | `load_attribution_policy` |
| Qualification thresholds | [../governance/policies/expert-qualification-thresholds.v0.1.json](../governance/policies/expert-qualification-thresholds.v0.1.json) | `load_qualification_policy` |
| Calibration task seeds | [../governance/policies/calibration-task-seeds.v0.1.json](../governance/policies/calibration-task-seeds.v0.1.json) | `load_calibration_seeds_policy` / `assert_calibration_seeds_resolvable` |

Constitutional requirements live in [GOVERNANCE.md](../GOVERNANCE.md). Changes to
qualification gates require a public decision record under `governance/decisions/`.

Module: `opencritique_registry.expert_policy`.

## Enforceable runtime behavior

- Qualification grants set `expires_at` from domain `expiry_days` (default 180).
- Expired qualifications are treated as inactive on task claim.
- Conflict disclosure is required; `disclosed` requires a description;
  `disqualifying` blocks submission.
- Duplicate primary/secondary assignment to the same adjudicator for one concern
  is refused (`assignment_guards`).
- Compensation policy stores schedule linkage fields only — never payment secrets.

## Pilot task flow (studio / registry)

1. Seed calibration tasks from sample cases (see calibration-task-seeds policy).
2. Experts complete blinded calibration; scores authorize domain eligibility only.
3. Paid pilot adjudication uses blinded primary + tie-break flows already exposed
   by the registry / studio.
4. Natural-case tasks require affirmative rights clearance
   ([rights-memorandum.md](rights-memorandum.md)); do not substitute samples
   for natural DoD denominators on issues #6 / #7.

## Claim boundary

Qualification and compensation ops authorize **program readiness**, not reviewer
system ranking or precision/recall publication.
