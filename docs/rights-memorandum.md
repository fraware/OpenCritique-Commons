# Rights memorandum — first external benchmark path

Issue #7 / PR10.

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
Accordingly this repository imports **only synthetic rights-cleared maintainer
placeholders** labeled as such.

## Artifact classes (machine-readable)

| Class | Status in this release | Notes |
|---|---|---|
| Synthetic case metadata | Authorized (maintainer) | Apache-2.0 placeholders |
| Synthetic review fixtures | Authorized (maintainer) | No confidential text |
| Natural manuscript PDFs | **Not imported** | Pending written clearance |
| Natural figure binaries | **Not imported** | Pending written clearance |
| Derived OpenCritique records from natural text | **Not imported** | Require case-level grants |
| Performance / comparative claims | **Disabled** | `performance_claims_authorized=false` |

## Case-level requirements

Every imported case must have:

1. A rights record (see `corpus/rights/` and case `rights_classification`)
2. Source-artifact hash when real bytes exist
3. Explicit evaluation-use and redistribution flags
4. Attribution / share-alike / withdrawal notes when applicable

Import tooling (`opencritique_acquisition` ledger validators and registry
`require_use_grant`) **rejects** artifacts outside an approved rights profile.

## Unresolved questions (archived for counsel / maintainers)

1. Does PeerQA's dataset license cover linked PDF full text, or only QA pairs?
2. Are conference review texts redistributable under the same terms as papers?
3. What withdrawal SLA applies if an author objects after import?

Until written clarification is archived, natural material stays out of the public
corpus.

## Six candidate cases

See `cases/rights-candidates/` — six synthetic/rights-cleared placeholders with
case-level rights records. They exercise the authorization path without enabling
scientific performance claims.

## Claim boundary

`performance_claims_authorized` remains **false** in the acquisition ledger and
all related README / release notes for this workstream.
