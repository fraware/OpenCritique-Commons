# Document graph alpha

Versioned ingestion toolchain for manuscript structure:

- Toolchain id: `opencritique-document-graph`
- Version: `0.1.0-alpha`
- Module: `opencritique_schema.document_graph`

This is an engineering alpha for sample conformance. It does not authorize
scientific performance claims or natural-corpus completeness.

## Node kinds

Page, equation, figure, table, citation, and text_block nodes carry:

- page ranges and optional bounding boxes
- optional text / labels
- `extraction_confidence` and explicit `extraction_uncertainty`

## Page-image verification hooks

`PageImageVerificationHook` records rendered page artifacts, optional OCR text
hashes, and match status (`pending` / `matched` / `mismatched` / `unavailable` /
`blocked`). Hooks do not invent manuscript content.

## Anchor resolution uncertainty

`resolve_against_graph` returns an `AnchorResolutionSurface` that preserves
extraction uncertainty and **fail-closes** when security findings are marked
`block`. Uncertain extraction remains uncertain; unresolved stays unresolved.

## Security fixtures

Malicious / hidden-text fixtures under `fixtures/document_graph/` are for
regression only. They must never be treated as scientific manuscripts.
