# Matcher-audit measured denominators (issue #6)

Protocol: `matcher-audit-pilot-v0.1` ([matcher-audit-protocol.md](matcher-audit-protocol.md)).

## Claim boundary

Sample denominators exercise tooling only. They do **not** satisfy the ≥100
**natural** decision DoD on issue #6. `performance_claims_authorized` remains
false.

## Measured denominators (authorized sets)

| Population | Evidence class | Measured decisions available | Toward ≥100 natural DoD |
|---|---|---:|---|
| Maintainer-owned sample Coarse fixtures (`fixtures/coarse/reviews/`) | sample / conformance | 12 review fixtures (stratified audit draws from matcher decisions over these cases) | **No** — not natural |
| OpenReviewer sample fixtures (`fixtures/openreviewer/reviews/`) | sample / conformance | 5 review fixtures | **No** — not natural |
| Natural / PeerQA adjudicated decisions | natural | **0** (rights clearance negative finding; see [rights-clearance-status.md](rights-clearance-status.md)) | **Open** |

## Sampling notes

- Protocol target remains 100 match decisions **or** every available decision when
  fewer exist; reports must state the actual denominator and evidence class.
- Configuration gates may invalidate a matching policy on human audit; sample
  audits do not unlock comparative performance claims.
- Re-measure after any natural import (issue #7) or production adapter intake
  (issues #3 / #5) that yields authorized natural matcher decisions.

## Status for issue #6

Keep **open** until a rights-cleared natural population yields ≥100 audited
natural decisions under the published protocol.
