# OpenReviewer production fixtures (issue #5)

This tree holds **authentic, redistributable** OpenReviewer outputs when they
become available. It is intentionally empty of review payloads until then.

## Intake requirements

1. Affirmative rights clearance covering any embedded manuscript text
   ([rights-memorandum.md](../../docs/rights-memorandum.md); issue #7).
2. Authentic OpenReviewer outputs with pinned upstream commit / config.
3. Content hashes and rights record ids for every artifact in `MANIFEST.json`.
4. Conversion without hand-editing JSON; unresolved anchors stay unresolved.

## Layout

```text
fixtures/openreviewer/production/
  README.md                 # this file
  MANIFEST.json             # intake status + provenance (see schema)
  MANIFEST.schema.json      # JSON Schema for MANIFEST.json
  reviews/                  # authentic output JSON files (empty until intake)
```

## Claim boundary

`performance_claims_authorized` remains **false**. Production fixtures authorize
conversion-fidelity engineering checks only — never reviewer-quality claims.

## Current status

See `MANIFEST.json` (`status: blocked`). Sample-adapter conformance lives under
`fixtures/openreviewer/` (not this tree).
