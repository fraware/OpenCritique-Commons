# Coarse production fixtures (issue #3)

This tree holds **genuine, rights-cleared** Coarse production exports when they
become available. It is intentionally empty of review payloads until then.

## Intake requirements

1. Affirmative rights clearance covering any embedded manuscript text
   ([rights-memorandum.md](../../docs/rights-memorandum.md); issue #7).
2. At least **10** genuine Coarse exports (no fabricated reviews).
3. Pinned upstream Coarse commit / configuration recorded in `MANIFEST.json`.
4. Content hashes and rights record ids for every artifact.
5. Conversion without hand-editing JSON; unresolved quotes stay unresolved.

## Layout

```text
fixtures/coarse/production/
  README.md                 # this file
  MANIFEST.json             # intake status + provenance (see schema)
  MANIFEST.schema.json      # JSON Schema for MANIFEST.json
  reviews/                  # genuine export JSON files (empty until intake)
```

## Claim boundary

`performance_claims_authorized` remains **false**. Production fixtures authorize
conversion-fidelity engineering checks only — never reviewer-quality claims.

## Current status

See `MANIFEST.json` (`status: blocked`). Sample-adapter conformance lives under
`fixtures/coarse/` (not this tree).
