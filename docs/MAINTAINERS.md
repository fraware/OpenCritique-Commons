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

## Review ownership matrix

Path → role mapping is enforced in [`.github/CODEOWNERS`](../.github/CODEOWNERS).
Until a broader maintainer team exists, the repository owner `@fraware` is the
**interim** owner for every role. Second reviewers are named placeholders until
real GitHub handles are assigned; do not invent `@` handles in CODEOWNERS.

| Role | Paths (summary) | Interim owner | Second reviewer (placeholder) |
|---|---|---|---|
| evaluation-method | `src/opencritique_evaluation/` | `@fraware` | `TBD-external-evaluation` |
| scientific-schema | `schemas/` | `@fraware` | `TBD-external-schema` |
| rights/governance | `src/opencritique_acquisition/`, `corpus/rights/`, `docs/rights*` | `@fraware` | `TBD-external-rights` |
| security | `signing.py`, `trust.py`, `trust/` | `@fraware` | `TBD-external-security` |
| evaluation + security | `scripts/check_v09*`, `v09_gate_lib.py`, claim-auth / attestation / signed scorecard schemas, `scorecard.py`, `models.py` | `@fraware` | `TBD-external-security` (or evaluation) |

Replace each `TBD-*` placeholder with a real GitHub username or team in both this
table and CODEOWNERS when that reviewer joins. Until then, the PR author must
name a distinct human reviewer in the PR body for dual-role paths.

### Dual approval (claim-boundary / trust / scoring)

For PRs that touch **claim authorization**, **trust / signing**, or **scoring /
scorecard** surfaces (the “evaluation + security” rows above, plus related
schemas and gates):

1. **No author self-approval** — the author’s own review does not count.
2. **At least two distinct approvals** before merge (CODEOWNERS review plus one
   other maintainer or designated external reviewer).
3. If the only CODEOWNER is also the author, require an explicitly designated
   external reviewer in the PR body and wait for that approval.

Routine Tier 1–2 docs/adapter PRs outside those paths follow normal single
CODEOWNERS review once branch protection is enabled.

## Branch protection (GitHub settings checklist)

Configure on `main` (Settings → Branches → Branch protection rule). Status at
docs time: protection may not yet be enabled; treat this list as the required
maintainer action.

### Required status checks

From [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), require these
**core** jobs before merge:

- `lint`
- `test (3.12)` and `test (3.13)` (matrix legs)
- `packaging`
- `secret-scan`
- `publication-audit`
- `postgres`

Do **not** require `optional-openreviewer` until that job is stable.

Also enable:

- [ ] Require a pull request before merging
- [ ] Require approvals — **minimum 1** for ordinary paths; **minimum 2** for
      claim-boundary / trust / scoring (use rulesets or always require 2 while
      the team is thin)
- [ ] Dismiss stale pull request approvals when new commits are pushed
- [ ] Require review from Code Owners
- [ ] Require conversation resolution before merging
- [ ] Do not allow bypassing the above settings (restrict admin bypass)
- [ ] Require signed commits (or Vigilant mode for maintainers) for merge to
      `main`
- [ ] Include administrators (no silent force-push / unprotected merge)

After merge, verify ancestry on `origin/main`
(`git merge-base --is-ancestor <pr-head> origin/main`) rather than relying only
on a PR having been “merged” into a feature branch.

Constitutional overlap (separation of powers, ADR triggers) is summarized in
[GOVERNANCE.md](../GOVERNANCE.md).

## Security

Security reports follow [SECURITY.md](../SECURITY.md). Do not discuss active
incidents in public issues.
