# Cross-adapter conformance report

- Generated at: `2026-07-29T12:38:28.290977+00:00`
- Fixture kind: `maintainer_owned_sample_corpus`
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
- absent severity → informational severity with explicit unavailable note
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

## source=production (`coarse`)

- Status: `blocked`
- Fixture root: `C:/Users/mateo/OpenCritique-Commons/fixtures/coarse/production`
- Export count: 0
- Blocked reason: No genuine rights-cleared Coarse production exports available; sample fixtures remain under fixtures/coarse/. Tracked on issue #3; rights path on issue #7.

Production conversion fidelity only when status=ready; never reviewer-quality claims.

## source=production (`openreviewer`)

- Status: `blocked`
- Fixture root: `C:/Users/mateo/OpenCritique-Commons/fixtures/openreviewer/production`
- Export count: 0
- Blocked reason: No authentic redistributable OpenReviewer production outputs available; sample fixtures remain under fixtures/openreviewer/. Tracked on issue #5; rights path on issue #7.

Production conversion fidelity only when status=ready; never reviewer-quality claims.
