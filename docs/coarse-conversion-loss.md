# Coarse conversion-loss report

- Generated at: `2026-07-29T17:53:05.133213+00:00`
- Upstream contract: `coarse-review-contract-v1`
- Upstream repository: https://github.com/Davidvandijcke/coarse
- Sample adapter contract: `opencritique-sample-adapter-contract-v1`
- Fixture kind: `maintainer_owned_sample_corpus`
- Performance claims authorized: **False**

## Disclosure

Maintainer-owned sample fixtures exercise adapter compatibility only. They do not authorize precision, recall, or comparative performance claims.

## Compatibility matrix

| Contract | Status | Notes |
|---|---|---|
| `coarse-review-contract-v1` | supported | Sample-adapter contract fixtures from corpus/samples/; genuine production Coarse exports tracked on issue #3. |

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

## source=production (`coarse`)

- Status: `blocked`
- Fixture root: `C:/Users/mateo/OpenCritique-Commons/fixtures/coarse/production`
- Export count: 0
- Rights record count: 0
- Blocked reason: No genuine rights-cleared Coarse production exports available; sample fixtures remain under fixtures/coarse/. Tracked on issue #3; rights path on issue #7.

NOT READY: refuse production conversion-fidelity / readiness language until `status=ready` with ≥10 hashed exports (currently 0).

Production conversion fidelity only when status=ready; never reviewer-quality claims.
