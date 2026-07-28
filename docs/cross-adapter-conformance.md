# Cross-adapter conformance report

- Generated at: `2026-07-28T21:56:02.550123+00:00`
- Fixture kind: `synthetic_rights_cleared_maintainer`
- Performance claims authorized: **False**

Adapter conformance compares information preservation only. It does not validate reviewer quality or authorize performance claims.

## `coarse` (`coarse-review-contract-v1`)

### Preserved

- detailed_comments title/quote/feedback
- comment numbers via provenance material
- severity and confidence enums

### Normalized

- severity enum → Severity
- confidence enum → float

### Withheld / unavailable

- verified claims
- expert taxonomy

### Lost or omitted

- overall_feedback
- comment status
- review-level metadata

## `openreviewer` (`openreviewer-markdown-template-v1`)

### Preserved

- markdown body (via provenance hash)
- finding title/body when structured
- weakness bullets parsed from markdown
- venue_template
- recommendation_score when present (system metadata only)

### Normalized

- markdown weakness bullets → SubmittedConcern
- absent severity → informational placeholder with explicit unavailable note
- absent confidence → 0.0 with explicit unavailable note

### Withheld / unavailable

- severity when not supplied by OpenReviewer
- confidence when not supplied
- quote/page anchors when not supplied
- claim validity
- concern taxonomy beyond adapter.openreviewer.unclassified

### Lost or omitted

- narrative strengths / questions sections (not mapped to concerns)
- PDF extraction artifacts
- model sampling randomness (fixtures are frozen)
