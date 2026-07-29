# Rights memorandum — first external benchmark path

Issue #7. Sample-conformance path ships maintainer-owned manuscripts only.

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
under `corpus/samples/` for tooling conformance only. The formal negative finding
and checklist archive for the current investigation are in
[rights-clearance-status.md](rights-clearance-status.md).

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

## Approved-profile importer (command sequence)

When the first rights-cleared external case is ready, land it with the approved
profile importer (no fabricated manuscripts):

1. Place the manuscript bytes under a path inside the repo (or a vault path
   referenced by the profile) and compute SHA-256.
2. Write a case-level rights record under `corpus/rights/` with
   `natural_manuscript_imported=true`, `evaluation_use_authorized=true`, and
   `performance_claims_authorized=false`.
3. Author an approved-profile JSON (`profile_kind=natural`) binding
   `source_artifact_sha256`, grant fields, and `rights_record_path`.
4. Dry-run validate:

```bash
opencritique-acquisition validate-approved-profile path/to/approved-profile.json
opencritique-acquisition import-approved-profile path/to/approved-profile.json --dry-run
```

5. Persist only after counsel sign-off:

```bash
opencritique-acquisition import-approved-profile path/to/approved-profile.json --no-dry-run
```

Reject paths (already enforced): hash mismatch, missing grant flags, sample
profiles claiming natural import, natural profiles relying on “public
availability” alone, and any attempt to set `performance_claims_authorized=true`.

## Import rejection rules (already enforced)

Acquisition and registry paths **reject** artifacts that fail the approved profile:

- Missing or mismatched source-artifact SHA-256 / byte size
- Rights record without evaluation-use authorization
- Attempts to set `performance_claims_authorized=true` while the release gate is closed
- Natural imports without an archived grant (blocked by process and issue #7 DoD)
- Sample vs natural profile contamination (`natural_manuscript_imported` flag)

See `opencritique_acquisition.approved_profile` and ledger validators /
registry `require_use_grant`.

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
