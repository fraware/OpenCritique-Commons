# Local deployment

This repository ships a local reference stack for **sample-conformance** work.
Scientific-performance claims remain disabled in every local mode
(`performance_claims_authorized=false`).

There are two operator tracks (see [README.md](../README.md#two-operator-tracks)):

| Track | This doc | Related |
|---|---|---|
| Sample conformance (offline fixtures, Studio) | **Primary focus here** | Golden path in README; `bootstrap-sample-workspace` |
| Live upstream runners (optional Coarse BYOK / OpenReviewer import or HF) | Out of scope for Compose | [deployment-byok.md](deployment-byok.md); `opencritique runners …` |

Private live outputs under `runs/` are **not** production fixtures and do not
authorize claims or flip v0.9 gates.

## Requirements

- Python 3.12+
- Docker / Docker Compose
- Git Bash, WSL, or another POSIX shell for `scripts/check.sh` (on native
  Windows PowerShell, run `ruff` / `pyright` / `pytest` directly — see
  [CONTRIBUTING.md](../CONTRIBUTING.md#windows-and-packaging-notes))

## Start Postgres only

```bash
docker compose up -d postgres
```

## Start the reference stack

```bash
docker compose up --build
```

This starts:

- `postgres` on `localhost:5432`
- `registry` on `http://127.0.0.1:8000`

The registry container entrypoint runs `alembic upgrade head` (via
`opencritique_registry.migrate.upgrade_head`) before `serve`, so a fresh
`docker compose up --build` applies migrations automatically. `/readyz` still
fails closed until the database and artifact root are healthy.

## First-time operator setup

After the stack is up:

```bash
opencritique-registry bootstrap-sample-workspace \
  --database-url postgresql+psycopg://opencritique:opencritique@localhost:5432/opencritique
```

That command issues admin and adjudicator tokens, imports `cases/reference`,
seeds claimable adjudication tasks (including REF-01), and prints the Studio URL.
The golden path (synthetic Coarse convert → evaluate → scorecard → Studio) remains
the documented sample-conformance walkthrough.

Manual equivalent (if you prefer stepwise control):

```bash
# Only needed outside Compose, or to re-run migrations explicitly:
alembic upgrade head
opencritique-registry bootstrap-admin --database-url postgresql+psycopg://opencritique:opencritique@localhost:5432/opencritique
opencritique-registry import-reference cases/reference --project-root . \
  --database-url postgresql+psycopg://opencritique:opencritique@localhost:5432/opencritique
```

The registry validates startup on one shared path for local, BYOK, and Compose
entrypoints:

- `OPENCRITIQUE_DATABASE_URL` must be a valid SQLite or Postgres URL
- `OPENCRITIQUE_ARTIFACT_ROOT` must resolve to a writable directory
- `OPENCRITIQUE_PERFORMANCE_CLAIMS_AUTHORIZED` must remain unset or false
- `/healthz` reports process liveness; `/readyz` reports database and artifact
  readiness

## Studio

Open:

- `http://127.0.0.1:8000/studio`

Paste the adjudicator token from `bootstrap-sample-workspace`, connect, then
claim an adjudication task. The studio is intended for sample data and
development workflows only.

## Troubleshooting

- Migration drift: Compose re-applies migrations on each container start; you can
  also run `alembic upgrade head` locally and confirm `OPENCRITIQUE_DATABASE_URL`
  matches the database you are inspecting.
- Database reset during local iteration: stop the stack and remove the Compose
  volume with `docker compose down -v`.
- Artifact-path failures: ensure `OPENCRITIQUE_ARTIFACT_ROOT` is writable by the
  current user or container process; `/readyz` returns `503` when artifact-root
  validation fails.
- Empty Studio queue: run `opencritique-registry bootstrap-sample-workspace` (or
  seed tasks after `import-reference`).
- Permission or token issues in Studio: clear the session token, issue a new one
  with `bootstrap-sample-workspace` / `bootstrap-admin` or `/v1/tokens`, and reconnect.

## Release boundary

Passing local runtime checks demonstrates engineering conformance only. It does
not authorize scientific-performance claims, leaderboard use, or natural-corpus
evaluation claims.