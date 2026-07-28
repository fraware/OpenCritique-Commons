# Frozen JSON Schemas (v0.5.0a1)

Machine-readable schemas exported from `opencritique_schema.registry`.

- `inventory.json` — schema_id, schema_version, and model inventory
- `*.schema.json` — JSON Schema per persistent object type
- `GOLDEN_HASHES.json` — SHA-256 of canonical JSON for each artifact

Regenerate with:

```bash
opencritique schema export schemas
python -c "from tests._regen_schema_hashes import main; main()"
```

Or run the test suite; drift against `GOLDEN_HASHES.json` fails CI.
