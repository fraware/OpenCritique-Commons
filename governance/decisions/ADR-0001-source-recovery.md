# ADR-0001: Recovered source republication for v0.5.0a1

- **Status:** Accepted
- **Date:** 2026-07-28
- **Tags:** repository-truth, recovery, milestone-0

## Context

The public `main` branch declared an OpenCritique Commons `v0.5-alpha` /
`0.5.0a1` package surface, but the durable Git tree did not contain the
`src/opencritique_*` packages required for a fresh clone to install and run
tests. Temporary bootstrap transport (`.bootstrap/`, repair/publish workflows,
encoded wheel fragments) remained in the repository. A documented wheel SHA-256
(`fdb22e4266b973f277b06b950040ffbffb121913b2b1d127f1aec9440d9dbf83`) was never
verified against a readable distribution artifact available to maintainers.

ZIP-carved modules under a local inspection tree recovered most package source.
The reconstructed wheel central directory listed additional files that could not
be extracted because local file headers were corrupt, including:

- `opencritique_evaluation/engine.py`
- `opencritique_evaluation/cli.py`
- `opencritique_evaluation/__init__.py`
- `opencritique_registry/studio_assets/app.js`

## Decision

1. Treat carved modules as best-effort recovered source and republish them as
   ordinary files under `src/`.
2. Reimplement the unrecovered evaluation orchestration, evaluation CLI,
   package exports, and studio `app.js` against the recovered caller contracts
   (`adapters/coarse.py`, `evaluation/sensitivity.py`, schema CLI wiring, and
   studio HTML/API shapes).
3. Remove bootstrap/repair transport from the durable tree and absorb
   repository publication invariants (required paths present; prohibited paths
   absent).
4. Record that the published tree is **provisional recovered source** pending
   review. Cryptographic integrity of any historical wheel does not establish
   scientific correctness.
5. Do not merge further bootstrap/blob transport workflows.

## Consequences

- Fresh-clone install and `scripts/check.sh` become the Milestone 0 exit gate.
- Later PRs (schema freeze, novel determinations, migrations, adapters, rights)
  proceed only after this recovered tree is green.
- Role overlap during recovery is disclosed: the same engineering effort both
  recovered and rebuilt missing modules; this does **not** authorize independent
  scientific evaluation claims.
- Known gaps remain for later workstreams: Alembic history, natural-case
  fixtures, OpenAPI freeze, and richer release validation scripts described in
  historical package metadata.
