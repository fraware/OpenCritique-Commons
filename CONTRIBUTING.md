# Contributing to OpenCritique Commons

Thank you for helping keep scientific-critique infrastructure inspectable.

## Start here

1. Follow [START_HERE.md](START_HERE.md) — **Track A** (adapters / tool builders)
   or **Track B** (scientist / lab pilots). Both are first-class.
2. Pick a reading load from
   [docs/CONTRIBUTING_TIERS.md](docs/CONTRIBUTING_TIERS.md) (typo/docs vs
   adapters/runners vs schema/governance). Do not feel required to read all
   governance docs for a Tier 1 change.
3. Confirm the change does **not** authorize scientific performance claims
   (`performance_claims_authorized` stays false).
4. Prefer a linked issue. External-validity work on issues #3–#7 and #14 stays
   blocked until hard DoD evidence lands; do not invent natural corpus or
   fabricate production adapter exports.
5. Join discussion via [docs/COMMUNITY.md](docs/COMMUNITY.md). Security reports
   go to [SECURITY.md](SECURITY.md), not public issues.

Deep policy (when your tier requires it): [GOVERNANCE.md](GOVERNANCE.md),
[docs/REPOSITORY_PUBLICATION.md](docs/REPOSITORY_PUBLICATION.md), and
[docs/MILESTONES.md](docs/MILESTONES.md).

## Packages

Editable install exposes eight packages under `src/`:

| Package | Role |
|---|---|
| `opencritique_schema` | Shared critique schemas |
| `opencritique_registry` | Registry API, rights, studio, appeals |
| `opencritique_evaluation` | Matching, scoring, signing |
| `opencritique_adapters` | Coarse / OpenReviewer bridges |
| `opencritique_acquisition` | Rights-aware acquisition ledger |
| `opencritique_ingestion` | Markdown/LaTeX/PDF → document graph |
| `opencritique_verification` | Deterministic table/citation/Python checks |
| `opencritique_runners` | Optional live Coarse / OpenReviewer runners (`opencritique runners`) |

Package/engineering version is **`0.6.0a0`**. Schema freeze identity remains
**`0.5.0a1`** (golden hashes).

### Extending adapters and runners

- Third-adapter tutorial + skeleton:
  [docs/adapter-authoring.md](docs/adapter-authoring.md) and
  [`templates/adapter-skeleton/`](templates/adapter-skeleton/).
- Live runner plugin contract:
  [docs/runner-plugins.md](docs/runner-plugins.md)
  (`LiveRunnerPlugin` in `opencritique_runners.protocol`).
- Keep `[live-coarse]` / `[live-openreviewer]` extras optional; default install
  must not pull paid-API or GPU stacks.

## Development setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
bash scripts/check.sh
```

### Windows and packaging notes

- **Shell for `scripts/check.sh`:** use Git Bash or WSL. Native PowerShell does
  not run the bash script; on PowerShell run the same gates piecewise:
  `ruff check src tests scripts`, `pyright`, and `pytest`.
- **Live Coarse demos:** prefer
  [`scripts/live_pipeline_demo.ps1`](scripts/live_pipeline_demo.ps1) on
  PowerShell, or [`scripts/live_pipeline_demo.sh`](scripts/live_pipeline_demo.sh)
  under Git Bash/WSL. See [docs/deployment-byok.md](docs/deployment-byok.md).
- **ASCII-safe CLI:** runner help/banners stay ASCII (no smart quotes) so Windows
  consoles do not garble output.
- **Default CI:** mocked runner tests only — never paid upstream calls on
  push/PR. Optional manual
  [`.github/workflows/live-coarse-smoke.yml`](.github/workflows/live-coarse-smoke.yml)
  (`workflow_dispatch`) skips when BYOK/OpenAI secrets are absent.
- **Wheel/sdist:** `python -m build` must keep studio assets, OpenAPI, migrations,
  deployment docs, and trust store on the packaging job path (see CI
  `packaging` job).

Operator entry points:

- Local stack (sample conformance): [docs/deployment-local.md](docs/deployment-local.md)
- BYOK / live Coarse: [docs/deployment-byok.md](docs/deployment-byok.md)
  (registry credential gate **and** Coarse live runner via `[live-coarse]`;
  still **not** OpenReviewer; still **not** quality claims)
- Signing / trust store: [docs/signing-governance.md](docs/signing-governance.md)

### Secrets and `.env`

Never commit `.env` or API keys (`.env` / `.env.*` are gitignored). For live
Coarse, set `OPENCRITIQUE_BYOK_API_KEY` (or `OPENAI_API_KEY` as alias when BYOK
is unset) and optionally `OPENCRITIQUE_BYOK_PROVIDER_ID`. If a key is exposed,
rotate it with the provider. Do not print keys in logs, review JSON, or docs.

### Working-tree hygiene

Keep local residue **untracked** (covered by [`.gitignore`](.gitignore)):

| Path / pattern | Why |
|---|---|
| `opencritique.db` / `*.db` / `*.sqlite*` | Local registry SQLite |
| `runs/` | Private live / demo exports — not production fixtures |
| `/issue[0-9]*.md` | Local scratch notes |
| `.env`, `*.private.pem` | Secrets and signing material |
| `.demo-e2e/`, `.runtime-live/`, `_inspect_wheel/` | Operator-local smoke artifacts |

Do not add these to commits or PR branches. Private `runs/` never auto-promote
to `fixtures/*/production/`.

### Golden path (sample vision)

Follow the [README golden path](README.md#golden-path-sample-vision) or
[START_HERE.md](START_HERE.md) for the documented newcomer sequence (still
valid; offline fixtures only):

1. `pip install -e ".[dev]"` and `scripts/check.sh`
2. Coarse synthetic convert → `opencritique evaluation run` → scorecard
   (`NOT AUTHORIZED`)
3. `opencritique-registry bootstrap-sample-workspace` → serve → `/studio` →
   claim/submit on REF-01

Keep explicit non-claims: sample ≠ production authenticity ≠ scientific
performance. Private live outputs under `runs/` are **not** production fixtures
and do not move v0.9 gates to GO.

### Database URL

Registry services and Alembic read `OPENCRITIQUE_DATABASE_URL`.

- Default (local): `sqlite:///./opencritique.db`
- Postgres (Compose): start with `docker compose up -d postgres`, then:

```bash
export OPENCRITIQUE_DATABASE_URL=postgresql+psycopg://opencritique:opencritique@localhost:5432/opencritique
alembic upgrade head
```

Do not use `Base.metadata.create_all` for initialization; prefer `opencritique registry init`
(which runs `alembic upgrade head`) or Alembic directly.

## Commit convention

Use concise, imperative subjects. Prefer a prefix when it clarifies intent:

- `fix:` — bug fixes and restorations
- `feat:` — additive capability within an approved workstream
- `docs:` — documentation only
- `test:` — tests only
- `chore:` — tooling, CI, and repository hygiene
- `refactor:` — internal structure without behavior change

Explain *why* in the body when the change is non-obvious. Do not amend published
history or force-push shared branches.

## Pull requests

Use the repository PR template. Every PR must:

- state scope and out-of-scope items;
- disclose role overlaps during alpha staffing;
- include verification commands actually run;
- keep scientific-performance claims disabled unless an authorized gate is met;
- avoid committing transport residue (`.bootstrap/`, repair publish workflows,
  `_inspect_wheel/`, private keys, local scratch `issue*.md` notes,
  `opencritique.db`, or `runs/` dumps).

Newcomers: link [START_HERE.md](START_HERE.md). Adapter PRs: see also
[docs/compatibility-checklist.md](docs/compatibility-checklist.md) and
[docs/community-adapters.md](docs/community-adapters.md). Before opening an
adapter PR, run
`python scripts/check_adapter_compatibility.py` on the adapter path (or
`--registry docs/community-adapters.json` when updating the registry).

## Architecture decisions

Normative process and architecture choices belong under
`governance/decisions/` as append-only ADRs. Do not silently reshape frozen
schema names; file an ADR instead.

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
