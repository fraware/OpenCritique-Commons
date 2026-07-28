# Coarse conversion-loss report

- Generated at: `2026-07-28T21:55:56.502266+00:00`
- Upstream contract: `coarse-review-contract-v1`
- Upstream repository: https://github.com/Davidvandijcke/coarse
- Upstream commit pin: `9f3c2a1b8e7d6c5a4b3e2f1d0c9b8a7e6f5d4c3b`
- Fixture kind: `synthetic_rights_cleared_maintainer`
- Performance claims authorized: **False**

## Disclosure

Synthetic maintainer fixtures exercise adapter compatibility only. They do not authorize precision, recall, or comparative performance claims.

## Compatibility matrix

| Contract | Status | Notes |
|---|---|---|
| `coarse-review-contract-v1` | supported | Synthetic contract fixtures; genuine production exports still pending. |

## Aggregate quotation resolution

- Total quotations: 13
- Exact: 12 (0.923)
- Normalized: 0 (0.000)
- Ambiguous: 0
- Unresolved: 1

Exact and normalized rates are reported separately.
Unresolved quotations remain unresolved.

## Omitted / provisional fields

- `detailed_comments[].status`
- `overall_feedback`
- `title|domain|taxonomy|date|language`
- `claim reconstruction`

## Contract field inventory

- `review`: title, domain, taxonomy, date, overall_feedback, detailed_comments, language
- `overall_feedback`: summary, assessment, issues, recommendation, revision_targets
- `detailed_comment`: number, title, quote, feedback, status, severity, confidence

## Per-case recovery

| Case | Comments | Recovered numbers | Unresolved quotes |
|---|---:|---|---:|
| `occase_synth_econ_01` | 2 | 1, 2 | 0 |
| `occase_synth_econ_02` | 1 | 1 | 0 |
| `occase_synth_ml_01` | 1 | 1 | 0 |
| `occase_synth_ml_02` | 1 | 1 | 0 |
| `occase_synth_theory_01` | 1 | 1 | 0 |
| `occase_synth_theory_02` | 1 | 1 | 0 |
| `occase_synth_fig_01` | 1 | 1 | 0 |
| `occase_synth_table_01` | 1 | 1 | 0 |
| `occase_synth_multi_01` | 1 | 1 | 0 |
| `occase_synth_multi_02` | 1 | 1 | 0 |
| `occase_synth_stats_03` | 1 | 1 | 1 |
| `occase_synth_ml_03` | 1 | 1 | 0 |
