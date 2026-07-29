# Rights memorandum — first external benchmark path

Issue #7 / sample-conformance path on `main`.

## Controlling principle

Public accessibility (arXiv links, open PDFs, public downloads) is **not**
authorization to copy, transform, benchmark, redistribute, or train on content.

## Preferred candidate source

**PeerQA** (and similar QA/review corpora) remains a preferred *investigation*
target subject to verification of:

- dataset owner and maintainers
- governing license for questions/annotations vs linked manuscripts
- PDF / figure / full-text redistribution terms
- model-training restrictions

At the time of this memorandum, **no PeerQA (or other natural) manuscript set has
completed affirmative rights clearance** for public OpenCritique import.
Accordingly this repository imports **maintainer-owned open sample manuscripts**
under `corpus/samples/` for tooling conformance only.

## Artifact classes (machine-readable)

| Class | Status in this release | Notes |
|---|---|---|
| Maintainer-owned sample manuscripts | Authorized (maintainer) | Apache-2.0 under `corpus/samples/` |
| Sample review fixtures | Authorized (maintainer) | Quotes only sample manuscript text |
| Natural manuscript PDFs | **Not imported** | Pending written clearance (issue #7) |
| Natural figure binaries | **Not imported** | Pending written clearance |
| Derived OpenCritique records from natural text | **Not imported** | Require case-level grants |
| Performance / comparative claims | **Disabled** | `performance_claims_authorized=false` |

## Clearance checklist (before any natural import)

Complete every row and archive evidence under `corpus/rights/` (or counsel vault
referenced from the ledger). Do not invent grants.

| Step | Required evidence | Owner |
|---|---|---|
| Identify artifact class | Manuscript PDF, figures, annotations, review text, derived JSON | Maintainer |
| Locate controlling license / ToS | URL + retrieved copy hash | Maintainer |
| Written grant for evaluation use | Signed email/letter or explicit license clause covering evaluation | Counsel / owner |
| Written grant for redistribution (if public) | Explicit redistribution or “public archive” permission | Counsel / owner |
| Training / model-use restriction check | Confirm whether training is forbidden even when eval is allowed | Counsel |
| Attribution / share-alike obligations | Text to copy into case rights record | Maintainer |
| Withdrawal / cancel contact | Named contact + SLA for post-import objection | Maintainer |
| Case-level rights record | `evaluation_use_authorized`, hashes, flags; `performance_claims_authorized=false` until §12 gate | Maintainer |
| Ledger entry | `AcquisitionLedger` status + source metadata | Maintainer |
| Import dry-run | Prove reject path for missing grant | CI / maintainer |

## Import rejection rules (already enforced)

Acquisition and registry paths **reject** artifacts that fail the approved profile:

- Missing or mismatched source-artifact SHA-256 / byte size
- Rights record without evaluation-use authorization
- Attempts to set `performance_claims_authorized=true` while the release gate is closed
- Natural imports without an archived grant (blocked by process and issue #7 DoD)

See `opencritique_acquisition` ledger validators and registry `require_use_grant`.

## Withdrawal / cancel path

1. Mark the acquisition source `withdrawn` or `cancelled` via acquisition CLI.
2. Retain append-only ledger history; do not silently rewrite hashes.
3. Remove or quarantine redistributable bytes from the public artifact root when
   the grant is revoked.
4. Document the incident reference on the rights record.

## Case-level requirements

Every imported case must have:

1. A rights record (see `corpus/rights/` and case `rights_classification`)
2. Source-artifact hash when real bytes exist
3. Explicit evaluation-use and redistribution flags
4. Attribution / share-alike / withdrawal notes when applicable

## What remains blocked until counsel / owner sign-off

- Any natural manuscript or figure binary
- Authentic Coarse / OpenReviewer production exports that embed uncleared text
  (issues #3 / #5)
- Scientific performance claims (#12 matrix / issue #7 DoD)

## Unresolved questions (archived for counsel / maintainers)

1. Does PeerQA's dataset license cover linked PDF full text, or only QA pairs?
2. Are conference review texts redistributable under the same terms as papers?
3. What withdrawal SLA applies if an author objects after import?

Until written clarification is archived, natural material stays out of the public
corpus.

## Six sample cases

See `cases/rights-candidates/` and `corpus/samples/` — six maintainer-authored
open manuscripts with case-level rights records, claims, concerns, and evidence.
They exercise the authorization path without enabling scientific performance
claims. Natural corpus import remains blocked on issue #7.

## Claim boundary

`performance_claims_authorized` remains **false** in the acquisition ledger and
all related README / release notes for this workstream.
