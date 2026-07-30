# BYOK deployment

BYOK means the operator provides model credentials and keeps them outside the
registry database and repository.

## What BYOK is (and is not)

- **Is:** a **credential gate** — startup requires operator-supplied provider
  identity and API key via environment variables (or a secrets manager). The
  registry refuses to become ready when those credentials are missing in
  `execution_mode=byok`.
- **Is also:** the credential that enables the **Coarse live runner**
  (`opencritique runners coarse` / `opencritique runners pipeline coarse`) when
  the optional `[live-coarse]` extra is installed. Coarse is BYO-key via
  OpenAI / OpenRouter-style models.
- **Is not:** a scientific quality claim, leaderboard unlock, or reviewer-quality
  ranking (`performance_claims_authorized=false`).
- **Is not:** OpenReviewer's inference backend. OpenReviewer is
  Llama-OpenReviewer-8B (Hugging Face / local GPU or Space export import). An
  OpenAI key does **not** run OpenReviewer.

Private live Coarse exports under `runs/` are operator-local evidence. They do
**not** auto-promote into `fixtures/*/production/` and do not satisfy production
authenticity gates (rights + volume) on their own.

## Principles

- do not persist provider secrets in OpenCritique tables
- pass provider credentials through environment variables or a secrets manager
- keep `performance_claims_authorized=false` (the release gate is closed)
- require the same startup validation path as local and Compose modes
- never write API keys into review JSON, MANIFESTs, or the database

## Env load order (local operators)

1. Process environment (wins)
2. Optional local `.env` via python-dotenv when installed (`override=False`)

Alias: if `OPENCRITIQUE_BYOK_API_KEY` is unset, `OPENAI_API_KEY` is copied into
it for convenience. Live Coarse commands fail closed when neither is set.

Never commit `.env` (gitignored). Do not print keys. If a key was exposed,
rotate it with the provider. See [SECURITY.md](../SECURITY.md).

## Minimal environment

```bash
export OPENCRITIQUE_DATABASE_URL=postgresql+psycopg://opencritique:opencritique@localhost:5432/opencritique
export OPENCRITIQUE_ARTIFACT_ROOT=./opencritique-artifacts
export OPENCRITIQUE_EXECUTION_MODE=byok
export OPENCRITIQUE_BYOK_PROVIDER_ID=openai   # or openrouter
export OPENCRITIQUE_BYOK_API_KEY=...          # do not commit
# Optional alias when BYOK key unset:
# export OPENAI_API_KEY=...
```

## Coarse live runner

Expected cost band for a short sample manuscript with `openai/gpt-4o` is typically
on the order of **low single-digit USD** (provider pricing changes; treat as a
rough operator budget, not a quote). Rate limits and model availability vary by
account.

```bash
pip install -e ".[live-coarse]"   # pins coarse-ink==1.8.0 (Davidvandijcke/coarse)

opencritique runners coarse \
  --manuscript corpus/samples/sample-econ-01/manuscript.md \
  --output runs/coarse/sample-econ-01.json \
  --model openai/gpt-4o

opencritique runners pipeline coarse \
  --manuscript corpus/samples/sample-econ-01/manuscript.md \
  --out-dir runs/pipeline/coarse-sample-econ-01

# Register the live export into Studio (evidence_class=private_live)
opencritique-registry import-live-run \
  --from runs/pipeline/coarse-sample-econ-01 \
  --manuscript corpus/samples/sample-econ-01/manuscript.md
# or: opencritique runners pipeline coarse ... --register
```

See also `scripts/live_pipeline_demo.ps1` / `scripts/live_pipeline_demo.sh`
(exit codes + artifact checklist under `runs/`). Default CI uses mocked unit
tests and does **not** call paid APIs.

### Failure modes (actionable)

| Symptom | Likely cause | Fix |
|---|---|---|
| Missing key / BYOK error | Neither `OPENCRITIQUE_BYOK_API_KEY` nor `OPENAI_API_KEY` set | Set env or local `.env` (never commit); see above |
| `coarse` not installed | Optional extra missing | `pip install -e ".[live-coarse]"` |
| Model not found / invalid | Wrong litellm model id or account access | Check `--model` (e.g. `openai/gpt-4o`) |
| 429 / rate limit | Provider throttle | Wait / retry; lower concurrency |
| 401 / 403 | Bad or revoked key | Rotate with the provider; do not paste keys into issues |
| OpenReviewer + OpenAI key | Wrong backend expectation | OpenAI ≠ OpenReviewer; use `--from-export` ([openreviewer-space-import.md](openreviewer-space-import.md)) |

CLI errors redact key-shaped substrings. Never print or commit API keys.

Private Coarse exports under `runs/` stamp `evidence_class=private_live` and
`performance_claims_authorized=false`. They are **not** production fixtures and
do not satisfy `scripts/check_v09_gates.py`.

### Manual paid verification (operators only)

Last verified note for maintainers: record date + model id in an operator log
**without** secrets after a successful `scripts/live_pipeline_demo.*` run. Do
not put keys or full response dumps in git.

## OpenReviewer (not BYOK)

OpenReviewer does **not** use `OPENCRITIQUE_BYOK_API_KEY` / `OPENAI_API_KEY`:

```bash
# Import mode (no GPU) — preferred for most operators
opencritique runners openreviewer \
  --from-export path/to/space-or-local-export.json \
  --output runs/openreviewer/export.json

# Optional HF local (GPU): pip install -e ".[live-openreviewer]"
# opencritique runners openreviewer --manuscript path/to/paper.md \
#   --output runs/openreviewer/hf-local.json
```

Full cookbook: [openreviewer-space-import.md](openreviewer-space-import.md).
Shared Studio handoff: `opencritique-registry import-live-run --from …`.

## Run (registry)

```bash
alembic upgrade head
uvicorn opencritique_registry.api:app --host 0.0.0.0 --port 8000
```

BYOK startup fails closed when:

- `OPENCRITIQUE_BYOK_PROVIDER_ID` is missing
- `OPENCRITIQUE_BYOK_API_KEY` is missing (and no `OPENAI_API_KEY` alias)
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

Hosted deployment remains an out-of-repo operational responsibility (issue #18).
This repository ships a Compose reference stack so operators can run a local
equivalent; that stack is not a hosted production ops claim.

## Troubleshooting

- Ready check fails immediately: verify `OPENCRITIQUE_EXECUTION_MODE=byok`,
  `OPENCRITIQUE_BYOK_PROVIDER_ID`, and `OPENCRITIQUE_BYOK_API_KEY` (or
  `OPENAI_API_KEY` alias).
- Live Coarse fails with missing key: set BYOK or OpenAI key; do not commit `.env`.
- Token works in API clients but not Studio: clear browser session storage and
  reconnect with a fresh token.
- Artifact uploads fail with storage errors: check the permissions and free
  space for `OPENCRITIQUE_ARTIFACT_ROOT`.
- Postgres connection failures: verify the exact `OPENCRITIQUE_DATABASE_URL`
  string used by Alembic, the API server, and any import scripts.
