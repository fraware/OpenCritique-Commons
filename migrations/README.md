# Migrations

Alembic history for the OpenCritique registry database.

## Layout

- `alembic.ini` (repo root)
- `migrations/env.py`
- `migrations/versions/` — append-only revision scripts

## Commands

```bash
export OPENCRITIQUE_DATABASE_URL=sqlite:///./opencritique.db
alembic upgrade head
alembic current
```

Prefer Alembic (or `opencritique registry init`) over `Base.metadata.create_all`.
See [docs/deployment-local.md](../docs/deployment-local.md).

## Tests

`tests/test_migrations.py` covers:

1. Empty database → head
2. Previous-release stub (empty → current for the first migration)
3. Migrated table set equals SQLAlchemy metadata
