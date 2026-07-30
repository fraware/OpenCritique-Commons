# Coarse production fixtures (issue #3)

This tree holds **genuine, rights-cleared** Coarse production exports when they
become available. It is intentionally empty of review payloads until then.

Sample-adapter conformance (not production authenticity) lives under
`fixtures/coarse/` outside this tree.

## Intake requirements

1. Affirmative rights clearance covering any embedded manuscript text
   ([rights-memorandum.md](../../docs/rights-memorandum.md); issue #7).
2. At least **10** genuine Coarse exports (no fabricated reviews).
3. Pinned upstream Coarse commit / configuration recorded in `MANIFEST.json`
   (must not reuse the sample adapter contract id).
4. Content hashes, byte sizes, and rights record ids for every artifact.
5. Conversion without hand-editing JSON; unresolved quotes stay unresolved.

Validate a cleared package (refuses incomplete / unauthorized trees):

```bash
python scripts/ingest_production_adapter_exports.py validate \
  --adapter coarse --package /path/to/cleared-exports
python scripts/ingest_production_adapter_exports.py validate-tree --adapter coarse
```

## Layout

```text
fixtures/coarse/production/
  README.md                 # this file
  MANIFEST.json             # intake status + provenance (see schema)
  MANIFEST.schema.json      # JSON Schema for MANIFEST.json
  reviews/                  # genuine export JSON files (empty until intake)
```

### MANIFEST artifact fields (required for `status=ready`)

| Field | Requirement |
|---|---|
| `relative_path` | Under production root, typically `reviews/<id>.json` |
| `content_sha256` | Lowercase hex SHA-256 of exact file bytes |
| `byte_size` | Exact on-disk byte length |
| `rights_record_id` | Must be listed in top-level `rights_record_ids` |

Top-level ready requirements: `upstream_repository`, `upstream_commit_or_config`
(not a sample contract id), `retrieval_date`, ≥10 `artifacts`, matching on-disk
`reviews/*.json`, `performance_claims_authorized=false`. READY without the
minimum export count fails closed in CI.

## Claim boundary

`performance_claims_authorized` remains **false**. Production fixtures authorize
conversion-fidelity engineering checks only — never reviewer-quality claims.

Private live Coarse runs (`opencritique runners coarse` / `pipeline coarse`,
outputs under `runs/`) are **operator-local** (`evidence_class=private_live`).
They are **not** production fixtures and must not be auto-promoted into this
tree. See [adapter-authenticity.md](../../docs/adapter-authenticity.md).

## Current status

See `MANIFEST.json` (`status: blocked`). Do not invent natural evidence or fake
exports to clear this tree.
