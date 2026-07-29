# Local deployment

This repository ships a local reference stack for sample-conformance work.
Scientific-performance claims remain disabled in every local mode.

## Requirements

- Python 3.12+
- Docker / Docker Compose
- Git Bash or another POSIX shell for `scripts/check.sh`

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

## First-time database setup

```bash
alembic upgrade head
opencritique-registry bootstrap-admin --database-url postgresql+psycopg://opencritique:opencritique@localhost:5432/opencritique
```

The registry now validates startup on one shared path for local, BYOK, and
Compose entrypoints:

- `OPENCRITIQUE_DATABASE_URL` must be a valid SQLite or Postgres URL
- `OPENCRITIQUE_ARTIFACT_ROOT` must resolve to a writable directory
- `OPENCRITIQUE_PERFORMANCE_CLAIMS_AUTHORIZED` must remain unset or false
- `/healthz` reports process liveness; `/readyz` reports database and artifact
  readiness

## Import sample reference cases

```bash
opencritique-registry import-reference cases/reference --project-root . --database-url postgresql+psycopg://opencritique:opencritique@localhost:5432/opencritique
```

## Studio

Open:

- `http://127.0.0.1:8000/studio`

The studio is intended for sample data and development workflows only.

## Troubleshooting

- Migration drift: run `alembic upgrade head` again and confirm
  `OPENCRITIQUE_DATABASE_URL` matches the database you are inspecting.
- Database reset during local iteration: stop the stack and remove the Compose
  volume with `docker compose down -v`.
- Artifact-path failures: ensure `OPENCRITIQUE_ARTIFACT_ROOT` is writable by the
  current user or container process; `/readyz` returns `503` when artifact-root
  validation fails.
- Permission or token issues in Studio: clear the session token, issue a new one
  with `opencritique-registry bootstrap-admin` or `/v1/tokens`, and reconnect.

## Release boundary

Passing local runtime checks demonstrates engineering conformance only. It does
not authorize scientific-performance claims, leaderboard use, or natural-corpus
evaluation claims.
