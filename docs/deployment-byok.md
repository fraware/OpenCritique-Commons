# BYOK deployment

BYOK means the operator provides model credentials and keeps them outside the
registry database and repository.

## Principles

- do not persist provider secrets in OpenCritique tables
- pass provider credentials through environment variables or a secrets manager
- keep `performance_claims_authorized=false` unless a separate policy process says otherwise
- require the same startup validation path as local and Compose modes

## Minimal environment

```bash
export OPENCRITIQUE_DATABASE_URL=postgresql+psycopg://opencritique:opencritique@localhost:5432/opencritique
export OPENCRITIQUE_ARTIFACT_ROOT=./opencritique-artifacts
export OPENCRITIQUE_EXECUTION_MODE=byok
export OPENCRITIQUE_BYOK_PROVIDER_ID=example-provider
export OPENCRITIQUE_BYOK_API_KEY=...   # do not commit
```

## Run

```bash
alembic upgrade head
uvicorn opencritique_registry.api:app --host 0.0.0.0 --port 8000
```

BYOK startup fails closed when:

- `OPENCRITIQUE_BYOK_PROVIDER_ID` is missing
- `OPENCRITIQUE_BYOK_API_KEY` is missing
- the database URL is invalid
- the artifact root is not writable
- `OPENCRITIQUE_PERFORMANCE_CLAIMS_AUTHORIZED=true`

Use `http://127.0.0.1:8000/readyz` after startup to confirm database and
artifact readiness.

## Non-persistence guarantee

The BYOK provider identifier may appear in runtime configuration, but model
credentials must not be written to registry tables, intake records, or verifier
manifests. Only pass provider secrets via process environment or an external
secret manager; do not place them in manifests, JSON payloads, or repository
files.

## Operational note

Hosted deployment remains an out-of-repo operational responsibility, but this
repository now ships a Compose reference stack so hosted mode is not described
as a stub.

## Troubleshooting

- Ready check fails immediately: verify `OPENCRITIQUE_EXECUTION_MODE=byok`,
  `OPENCRITIQUE_BYOK_PROVIDER_ID`, and `OPENCRITIQUE_BYOK_API_KEY`.
- Token works in API clients but not Studio: clear browser session storage and
  reconnect with a fresh token.
- Artifact uploads fail with storage errors: check the permissions and free
  space for `OPENCRITIQUE_ARTIFACT_ROOT`.
- Postgres connection failures: verify the exact `OPENCRITIQUE_DATABASE_URL`
  string used by Alembic, the API server, and any import scripts.
