# Milestones and scientific gates

Honest tracking after Waves 0–1 engineering completeness and the development
signing ceremony (Wave 4.1). Annotated tag target: `v0.5.0a1`.

Scientific performance claims remain **disabled** until the claim-authorization
matrix (§12) and v1.0 gate (§14) are satisfied with natural adjudicated evidence.

**No-stubs policy:** shipped paths must run in CI without `|| true` carve-outs or
empty OpenAPI/trust scaffolds. Remaining scientific gaps are blocked issues with
hard DoD—not apologetic placeholders for features already claimed as done.

## Milestone status

| Milestone | Release target | Exit focus | Status |
|---|---|---|---|
| 0 | `v0.5.0a1` | Fresh-clone gate, source tree, process scaffolding | **Met** on `main` (PR #13); tag when CI-green |
| 1 | `v0.6-alpha` | Durable kernel: schema freeze, OpenAPI freeze, Alembic-only init, novel determinations, Coarse report, CLI | **Engineering met** — Coarse sample-conformance report present; genuine exports remain blocked (issue #3) |
| 2 | `v0.7-alpha` | Second adapter, signing governance, matcher-audit protocol, document graph alpha | **Engineering met with external blockers** — sample-only second adapter, matcher-audit, and ingestion/verifiers present; authentic OpenReviewer outputs (issue #5) and production keys (issue #4) remain blocked |
| 3 | `v0.8-alpha` | Rights path, sample cases, expert/studio maturity; **no performance claims** | **Mostly met for sample conformance** — owned sample corpus, import paths, appeals records, studio baseline, and deployment runbooks present; natural external rights path remains blocked (issue #7) |
| 4 | `v0.9-beta` | 40 natural cases, 2 profiles, independent adjudication, holdout, pilot scorecards | **Not met** |
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

## Runtime release checklist

- `scripts/check.sh` passes on a clean checkout.
- `/healthz` returns liveness and `/readyz` confirms database plus artifact-root
  readiness for the selected execution mode.
- Local, BYOK, and Compose startup paths share one validation contract.
- Reference sample cases import, ingest, and deterministic verifier smoke paths
  succeed.
- Packaging and CI treat studio assets, frozen API/schema artifacts, migrations,
  and deployment docs as engineering-release surfaces.

These checks authorize engineering release quality only. They do **not**
authorize scientific-performance claims, natural-corpus claims, or public model
leaderboards.

## §14 v1.0 gate tracking

| Gate element | Status |
|---|---|
| Governance / ADRs / CoC / license | Present (alpha) |
| Rolling holdout + natural adjudicated corpus (≥40 public claim cases) | **Missing** |
| Four deployment modes (local / hosted / BYOK / external) | Local + BYOK runbooks and Compose reference stack present; hosted production ops still external |
| Appeals process | Append-only appeal/correction records present for registry determinations |
| Ecosystem adapters with authentic redistributable outputs | **Partial** (interfaces + synthetic fixtures) |
| Security review of production signing keys | **Pending** (development keys only; issue #4) |
| Matcher-audit gate on production configs | Protocol present; natural pilot volume **missing** (issue #6) |

## Honest gaps carried forward (blocked issues)

1. Genuine Coarse production exports — issue #3
2. Authentic OpenReviewer redistributable outputs — issue #5
3. Natural rights-cleared manuscript corpus — issue #7
4. Production signing ceremony — issue #4 (development channel populated)
5. Matcher-audit pilot ≥100 **natural** decisions — issue #6

Until these close, release notes and README must not assert scientific reviewer performance.
