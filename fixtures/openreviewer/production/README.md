# OpenReviewer production fixtures (issue #5)

This tree holds **authentic, redistributable** OpenReviewer outputs when they
become available. It is intentionally empty of review payloads until then.

Sample-adapter conformance (not production authenticity) lives under
`fixtures/openreviewer/` outside this tree.

## Intake requirements

1. Affirmative rights clearance covering any embedded manuscript text
   ([rights-memorandum.md](../../docs/rights-memorandum.md); issue #7).
2. At least **5** authentic OpenReviewer outputs with pinned upstream commit /
   configuration (must not reuse the sample adapter contract id).
3. Content hashes, byte sizes, and rights record ids for every artifact in
   `MANIFEST.json`.
4. Conversion without hand-editing JSON; unresolved anchors stay unresolved.

Validate a cleared package (refuses incomplete / unauthorized trees):

```bash
python scripts/ingest_production_adapter_exports.py validate \
  --adapter openreviewer --package /path/to/cleared-exports
python scripts/ingest_production_adapter_exports.py validate-tree --adapter openreviewer
```

## Layout

```text
fixtures/openreviewer/production/
  README.md                 # this file
  MANIFEST.json             # intake status + provenance (see schema)
  MANIFEST.schema.json      # JSON Schema for MANIFEST.json
  reviews/                  # authentic output JSON files (empty until intake)
```

### MANIFEST artifact fields (required for `status=ready`)

| Field | Requirement |
|---|---|
| `relative_path` | Under production root, typically `reviews/<id>.json` |
| `content_sha256` | Lowercase hex SHA-256 of exact file bytes |
| `byte_size` | Exact on-disk byte length |
| `rights_record_id` | Must be listed in top-level `rights_record_ids` |

Top-level ready requirements: `upstream_repository`, `upstream_commit_or_config`
(not a sample contract id), `retrieval_date`, ≥5 `artifacts`, matching on-disk
`reviews/*.json`, `performance_claims_authorized=false`. READY without the
minimum export count fails closed in CI.

## Claim boundary

`performance_claims_authorized` remains **false**. Production fixtures authorize
conversion-fidelity engineering checks only — never reviewer-quality claims.

Private OpenReviewer imports / HF-local runs (`opencritique runners openreviewer`,
outputs under `runs/`) are **operator-local** (`evidence_class=private_live`).
They are **not** production fixtures and must not be auto-promoted into this
tree. OpenAI/BYOK keys do not run OpenReviewer. See
[adapter-authenticity.md](../../docs/adapter-authenticity.md).

## Current status

See `MANIFEST.json` (`status: blocked`). Do not invent natural evidence or fake
exports to clear this tree.
