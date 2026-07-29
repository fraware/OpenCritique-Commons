# Deferred: deeper document intelligence (#16)

Spec only. No OCR / theorem-graph / layout-anchor implementation in this
roadmap slice. Tracked as
[issue #16](https://github.com/fraware/OpenCritique-Commons/issues/16).

## Goal

Extend `opencritique_ingestion` beyond Markdown / LaTeX / text-layer PDF toward
layout-faithful scientific documents — without inventing natural corpus or
unlocking performance claims.

## In scope (when scheduled)

- OCR fidelity path for scanned pages with explicit uncertainty grades.
- Theorem / proof / definition graph extraction (LaTeX + text-layer PDF).
- Layout-dependent anchors (column, figure region, table cell) with fail-closed
  behavior when geometry is ambiguous.
- Regression fixtures from **maintainer-owned** samples only until rights
  clearance (#7).

## Hard DoD

- Documented extractor contract and uncertainty enum updates (ADR if schema
  names change).
- Deterministic tests for OCR/layout failure modes (blocked vs degraded).
- No silent acceptance of active PDF content (extends PDF security review).
- Sample fixtures only unless #7 grants exist.
- `performance_claims_authorized` remains false.

## Non-goals

- Natural manuscript import.
- Reviewer-quality claims.
- Empty stub packages.

## Dependencies / sequencing

After operator/developer/scientist cores (Phases A–C) and clear owners for
external-validity blockers (#3–#7). See [MILESTONES.md](MILESTONES.md).

## Cheap spike note (optional later)

A single layout-anchor uncertainty note on an owned sample PDF is acceptable as
a one-file spike; full OCR and theorem graphs wait for dedicated ownership.
