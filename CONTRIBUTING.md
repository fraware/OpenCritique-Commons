# Contributing to OpenCritique Commons

Thank you for helping keep scientific-critique infrastructure inspectable.

## Before you start

1. Read [GOVERNANCE.md](GOVERNANCE.md), [SECURITY.md](SECURITY.md), and
   [docs/REPOSITORY_PUBLICATION.md](docs/REPOSITORY_PUBLICATION.md).
2. Confirm the change does **not** authorize scientific performance claims.
3. Prefer a linked issue. External-validity work on issues #3–#7 and #14 stays
   blocked until hard DoD evidence lands; do not invent natural corpus or
   production keys.
4. Skim [docs/MILESTONES.md](docs/MILESTONES.md) for claim boundaries and the
   runtime release checklist.

## Packages

Editable install exposes seven packages under `src/`:

| Package | Role |
|---|---|
| `opencritique_schema` | Shared critique schemas |
| `opencritique_registry` | Registry API, rights, studio, appeals |
| `opencritique_evaluation` | Matching, scoring, signing |
| `opencritique_adapters` | Coarse / OpenReviewer bridges |
| `opencritique_acquisition` | Rights-aware acquisition ledger |
| `opencritique_ingestion` | Markdown/LaTeX/PDF → document graph |
| `opencritique_verification` | Deterministic table/citation/Python checks |

## Development setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
bash scripts/check.sh
```

Operator entry points:

- Local stack: [docs/deployment-local.md](docs/deployment-local.md)
- BYOK / bring-your-own-keys: [docs/deployment-byok.md](docs/deployment-byok.md)

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
  `_inspect_wheel/`, private keys).

## Architecture decisions

Normative process and architecture choices belong under
`governance/decisions/` as append-only ADRs. Do not silently reshape frozen
schema names; file an ADR instead.

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
