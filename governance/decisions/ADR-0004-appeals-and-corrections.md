# ADR-0004: Append-only appeals and corrections

- Status: Accepted
- Date: 2026-07-29
- Issues: #6, #7

## Decision

OpenCritique records **appeals** and **corrections** as append-only registry
events linked to a determination. Existing determinations and adjudications are
never silently rewritten in place.

## Why

- scientific disagreements and author follow-up need an immutable trail
- metadata corrections must be possible without mutating prior public records
- future scorecards need provenance over predecessor records

## Consequences

1. Registry API exposes append-only `appeal` and `correction` record creation.
2. Each record links to a determination and may reference a predecessor record.
3. Downstream policy may recompute successor determinations later, but this ADR
   only establishes immutable record capture.

## Non-goals

- silent mutation of prior determinations
- overwriting adjudication reasoning
- claiming that appeal adjudication on natural manuscripts is already complete
