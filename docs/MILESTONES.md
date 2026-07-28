# Milestones and scientific gates

Honest tracking after PR1–PR10 workstreams on `fix/restore-canonical-source`.

Scientific performance claims remain **disabled** until the claim-authorization
matrix (§12) and v1.0 gate (§14) are satisfied with natural adjudicated evidence.

## Milestone status

| Milestone | Release target | Exit focus | Status after this branch |
|---|---|---|---|
| 0 | recovered `v0.5` | Fresh-clone gate, source tree, process scaffolding | **Implemented in-tree** (tagging/`main` merge still a maintainer action) |
| 1 | `v0.6-alpha` | Durable kernel: schema freeze, migrations, novel determinations, Coarse report, CLI | **Largely met in-tree** — Coarse report uses **synthetic** fixtures (genuine exports still unavailable) |
| 2 | `v0.7-alpha` | Second adapter, signing governance, matcher-audit protocol, document graph alpha | **Largely met in-tree** — OpenReviewer adapter stubbed with synthetic fixtures; trust store has no production keys yet |
| 3 | `v0.8-alpha` | Rights path, 6 cases, expert/studio maturity; **no performance claims** | **Partial** — rights memorandum + 6 synthetic candidates shipped; natural PeerQA import **not** cleared; expert qualification maturity still thin |
| 4 | `v0.9-beta` | 40 natural cases, 2 profiles, independent adjudication, holdout, pilot scorecards | **Not met** — natural volume and adjudication gates remain open |
| 5 | `v1.0` | Full §14 gate | **Not met** |

## §12 Claim-authorization matrix

| Claim class | Authorized now? | Required evidence |
|---|---|---|
| Infrastructure / schema / adapter conformance | Yes (descriptive) | Fixtures + tests; must not be framed as reviewer quality |
| Synthetic matching / conversion demos | Yes (descriptive only) | Explicit non-performance disclosure |
| Precision / recall / severity-weighted metrics as scientific results | **No** | Expert-natural or live-private benchmarks, adjudicated, independent evaluation, minimum public claim cases |
| Comparative reviewer ranking / leaderboard claims | **No** | Same as above + matcher-audit gate passed |
| “Production Coarse compatibility” as quality endorsement | **No** | Compatibility ≠ correctness; genuine exports still pending |

Enforcement hooks already present:

- `BenchmarkManifest.performance_claim_authorized()`
- `AcquisitionLedger.performance_claims_authorized` (false)
- Scorecard disclosure text when unauthorized
- Rights memorandum + case-level rights records

## §14 v1.0 gate tracking

| Gate element | Status |
|---|---|
| Governance / ADRs / CoC / license | Present (alpha) |
| Rolling holdout + natural adjudicated corpus (≥40 public claim cases) | **Missing** |
| Three deployment modes (local / hosted / BYOK) mature | **Partial / missing** |
| Appeals process | **Missing** |
| Ecosystem adapters with authentic redistributable outputs | **Partial** (interfaces + synthetic fixtures) |
| Security review of production signing keys | **Pending** (ceremony not run; trust store empty of release keys) |
| Matcher-audit gate on production configs | Protocol present; natural pilot volume **missing** |

## Honest gaps carried forward

1. Genuine Coarse production exports unavailable — synthetic contract fixtures only (PR5).
2. Second reviewer (OpenReviewer) not executed end-to-end on redistributable natural PDFs (PR7).
3. Natural rights-cleared manuscript corpus not yet importable (PR10).
4. Production signing keys not yet published (PR6 trust store scaffold only).
5. Matcher-audit pilot lacks ≥100 **natural** decisions (PR9 protocol ready).

Until these close, release notes and README must not assert scientific reviewer performance.
