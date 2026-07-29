# OpenAPI

Frozen Registry HTTP OpenAPI lives here:

- [`registry.openapi.json`](registry.openapi.json) — generated from
  `opencritique_registry.api:create_app()` (includes expert and matcher-audit routes;
  studio HTML routes are excluded via `include_in_schema=False`)

Regenerate and check drift:

```bash
python scripts/export_openapi.py
pytest -q tests/test_openapi_freeze.py
```

Object schemas for the **v0.5 schema freeze** (`SCHEMA_FREEZE_RELEASE = 0.5.0a1`)
live under [`schemas/`](../schemas/) and are gated by golden hash tests. Package
engineering version may advance independently (currently `0.6.0a0`).
