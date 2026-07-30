# Matcher-audit measured denominators (issue #6)

Protocol: `matcher-audit-pilot-v0.1` ([matcher-audit-protocol.md](matcher-audit-protocol.md)).

## Claim boundary

Sample denominators exercise tooling only. They do **not** satisfy the ≥100
**natural** decision DoD on issue #6. `performance_claims_authorized` remains
false.

## Completed adjudication (gate #6)

Scientific gate #6 counts **completed adjudicated decisions**, not
`sampled_count`:

1. Unique `candidate_id` values across natural sessions
2. Two primary judgments from distinct auditors per candidate
3. Tie-break judgment when primaries disagree
4. Companion `*.agreement.json` (`AuditAgreementReport`) present and bound to
   the session `sample_id_hash`
5. Evidence class `natural`; claims locked
6. Verified `MatcherAuditCompletionAttestation` binding session IDs, judgment-set
   hash, and `completed_decision_count` (≥100)

A natural session manifest with `sampled_count=100` and zero judgments does
**not** satisfy the gate.

## Measured denominators (authorized sets)

| Population | Evidence class | Measured decisions available | Toward ≥100 natural DoD |
|---|---|---:|---|
| Maintainer-owned sample Coarse fixtures (`fixtures/coarse/reviews/`) | sample / conformance | 12 review fixtures (stratified audit draws from matcher decisions over these cases) | **No** — not natural |
| OpenReviewer sample fixtures (`fixtures/openreviewer/reviews/`) | sample / conformance | 5 review fixtures | **No** — not natural |
| Natural / PeerQA adjudicated decisions | natural | **0** (rights clearance negative finding; see [rights-clearance-status.md](rights-clearance-status.md)) | **Open** |

Recompute programmatically (never invents natural volume). Completed counts are
**discovered** from session manifests + agreement reports under
`corpus/matcher-audit/sessions/` (0 when the directory is empty or judgments are
absent):

```bash
python -c "from opencritique_evaluation.matcher_audit import measure_current_denominators, discover_natural_decision_count, discover_completed_matcher_audit; print(discover_natural_decision_count()); print(discover_completed_matcher_audit()); print(measure_current_denominators())"
```

`scripts/check_v09_scientific_gates.py` matcher-audit gate uses the same
completed-accounting path plus attestation verification.

## Session manifests

Stratified draws persist as `MatcherAuditSessionManifest` objects with:

- `evidence_class` (`sample` vs `natural`)
- `population_denominator` and `sampled_count` (declared sample size only)
- `configuration_hash` over the matcher config
- `natural_dod_met` (false for sample sessions; requires natural completed volume)

Companion agreement reports: `sessions/<stem>.agreement.json`.

Drop natural session JSON under `corpus/matcher-audit/sessions/` for gate
discovery. Sample sessions cannot mark `natural_dod_met=true` and do not count
toward the natural DoD.

## Sampling notes

- Protocol target remains 100 match decisions **or** every available decision when
  fewer exist; reports must state the actual denominator and evidence class.
- Configuration gates may invalidate a matching policy on human audit; sample
  audits do not unlock comparative performance claims.
- Re-measure after any natural import (issue #7) or production adapter intake
  (issues #3 / #5) that yields authorized natural matcher decisions.

## Status for issue #6

Keep **open** until a rights-cleared natural population yields ≥100 **completed**
adjudicated natural decisions under the published protocol, with a signed
completion attestation.
