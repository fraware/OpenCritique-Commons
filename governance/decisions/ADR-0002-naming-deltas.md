# ADR-0002: Freeze recovered naming deltas for v0.5

- **Status:** Accepted
- **Date:** 2026-07-28
- **Tags:** schema, naming, v0.5-freeze

## Context

Handoff section 5 and informal architecture notes use several names that differ
from the recovered v0.5.0a1 source tree:

| Informal / handoff name | Recovered name |
|-------------------------|----------------|
| `ManuscriptArtifact` | `Manuscript` + `ManuscriptVersion` with nested `ArtifactReference` |
| `Evidence` | `EvidenceItem` |
| `Scorecard` | `PublicScorecard` (plus `SignedScorecardEnvelope`) |
| Schema-level `Determination` | Registry ORM `DeterminationORM` / API `DeterminationView` for case concerns; evaluation `NovelConcernDetermination` for novel candidates |

Silently renaming or reshaping these types to match the informal vocabulary
would invalidate recovered fixtures, content hashes, and caller contracts.

## Decision

1. Freeze the recovered names for the v0.5 schema series.
2. Document the deltas in this ADR and in `docs/schema-compatibility.md`.
3. Register every persistent object under `opencritique.<RecoveredTypeName>` in
   `opencritique_schema.registry`.
4. Schedule additive aliases or renames only via a future major schema bump,
   accompanied by a new ADR and dual-read/dual-write if needed.

## Consequences

- JSON Schema exports and golden hashes use recovered class names.
- Novel-concern determinations are introduced as
  `NovelConcernDetermination` without renaming case-concern registry
  determinations.
- Downstream PRs must not reshape core schemas to fit one adapter.
