# Maintainer process

Operational expectations for people with write or triage access. Contributors
should read [COMMUNITY.md](COMMUNITY.md) and [START_HERE.md](../START_HERE.md);
this page is for maintainers.

## Triage SLA

Acknowledge new issues and pull requests within **72 hours** on business days
(comment, label, or request for info counts). Acknowledgment is not a merge
promise.

Suggested first labels:

- `needs-triage` until scoped
- `good first issue` / `help wanted` when appropriate
- `track-adapters` or `track-pilots` for contributor-funnel work
- `workstream-A` … `workstream-J` for engineering streams (see
  [`.github/labels.yml`](../.github/labels.yml))

Clear `needs-triage` once a maintainer has accepted or redirected the issue.

## First-pass review checklist

On every PR, review in this order:

1. **Claim boundary** — Does the change keep
   `performance_claims_authorized=false`? Does wording avoid unauthorized
   precision/recall, rankings, or “quality proven” language?
2. **Scope** — Is the PR focused? Are out-of-scope items listed?
3. **Evidence honesty** — No fabricated production MANIFESTs, natural counts, or
   fake rights clearance. Private `runs/` must not auto-promote to
   `fixtures/*/production/`.
4. **Hygiene** — No `opencritique.db`, `.env`, private keys, `runs/` dumps, or
   scratch `issue*.md` notes.
5. **Verification** — Commands in the PR body match what was run; CI green when
   required.
6. **North Star / ADR** — Schema or policy semantics unchanged, or an ADR is
   linked under `governance/decisions/`.

Use the repository [pull request template](../.github/PULL_REQUEST_TEMPLATE.md).
Point newcomers at [START_HERE.md](../START_HERE.md) and
[CONTRIBUTING_TIERS.md](CONTRIBUTING_TIERS.md) rather than requiring full
governance reading for Tier 1–2 changes.

## When to request an ADR

Request or author an ADR when the change:

- Renames or reinterprets frozen schema inventory
- Changes signing, trust-store, or rights policy
- Alters claim-authorization gates or milestone DoD
- Sets lasting community process that should be constitutional

Otherwise keep lightweight process in this file and [COMMUNITY.md](COMMUNITY.md).

## Claim-boundary enforcement

Hard fail (request changes or close):

- Setting or implying `performance_claims_authorized=true` without documented
  §12 / v0.9 evidence
- Shipping `status=ready` production MANIFESTs without rights + volume evidence
- Public language that equates sample or private_live evidence with scientific
  performance claims or production authenticity
- Committing secrets or uncleared manuscript text

When unsure, leave claims locked and ask the author to reword. Prefer linking
[docs/MILESTONES.md](MILESTONES.md) and
[docs/adapter-authenticity.md](adapter-authenticity.md).

## Office hours and recognition

- Host or rotate biweekly office hours as described in COMMUNITY.md.
- Credit merged contributors in release notes (Engineering / Adapters /
  Docs & pilots lanes — never “accuracy improved” without gates).
- Optional all-contributors tooling may be added later; do not block merges on it.

## Security

Security reports follow [SECURITY.md](../SECURITY.md). Do not discuss active
incidents in public issues.
