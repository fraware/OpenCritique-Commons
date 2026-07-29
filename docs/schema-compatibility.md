# Schema compatibility and deprecation

This policy governs the frozen v0.5 OpenCritique Commons schemas
(`SCHEMA_FREEZE_RELEASE = 0.5.0a1`). Package/engineering releases (for example
`0.6.0a0`) may advance without changing freeze identity.

## Identifiers

Every persistent object type has:

- a stable `schema_id` of the form `opencritique.<TypeName>`
- a `schema_version` string registered in `opencritique_schema.registry`

Record-bearing schema models also embed `schema_version` on instances
(currently `0.1.0` for `RecordBase` types). Evaluation and adapter manifests use
their own document version fields (`0.1`).

## Compatibility classes

| Change | Allowed in | Requirement |
|--------|------------|-------------|
| Add optional field with default | Patch / minor | Document in release notes; update golden schemas |
| Add new enum member used only by new writers | Minor | Consumers must ignore unknown members fail-closed where safety requires |
| Tighten validation / remove field | Major | New `schema_version` + ADR |
| Rename type or `schema_id` | Major | ADR; additive aliases preferred before removal |
| Change canonicalization rules | Major | ADR; invalidate prior content hashes |

## Deprecation

1. Mark the old field or alias in docs and release notes.
2. Keep accepting the deprecated form for at least one minor series.
3. Emit structured warnings in tooling where practical.
4. Remove only on a major schema bump.

Silent reshaping to match a single reviewer system is forbidden. Adapter loss
must remain explicit.

## Malformed input

Validation failures raise typed errors (`pydantic.ValidationError` at the model
boundary; `SchemaValidationError` when validating through the schema registry).
Fixtures that omit required fields, violate ID patterns, or break graph
invariants must fail closed — never coerce into a “best effort” object.

## Naming freeze

Recovered type names are frozen for v0.5. See ADR-0002 for the mapping between
handoff informal names and recovered identifiers (`Manuscript` /
`ArtifactReference`, `EvidenceItem`, `PublicScorecard`, registry `Determination`).
