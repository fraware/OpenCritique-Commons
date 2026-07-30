# Contributing tiers

Not every change requires the full policy stack. Use this page to find the
**minimum** reading for your change class. Deep process still lives in
[GOVERNANCE.md](../GOVERNANCE.md); newcomers should not need to read everything
first.

Start with [START_HERE.md](../START_HERE.md) (Track A adapters or Track B
pilots). Then pick a tier below.

---

## Tier 1 — Typos, docs, and newcomer friction

**In scope:** README/START_HERE clarity, comment fixes, doc cross-links, example
wording that does not change claim language.

**Must read:**

1. [START_HERE.md](../START_HERE.md) (skim)
2. [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md)
3. Claim boundary: do not weaken “claims unauthorized” language

**Optional:** [CONTRIBUTING.md](../CONTRIBUTING.md) setup if you run checks.

**Issue template:** Docs improvement.

---

## Tier 2 — Adapters, runners, evaluation tests, fixtures (sample)

**In scope:** Adapter maps/convert, skeleton stubs, loss reports, runner plugins,
sample fixtures, claims-locked tests, Studio smoke docs.

**Must read:**

1. [START_HERE.md](../START_HERE.md) Track A or B as applicable
2. [CONTRIBUTING.md](../CONTRIBUTING.md)
3. [docs/adapter-authoring.md](adapter-authoring.md) and/or
   [docs/runner-plugins.md](runner-plugins.md)
4. [docs/adapter-authenticity.md](adapter-authenticity.md) (sample vs production;
   never fabricate `MANIFEST` ready)
5. Claim boundary checkboxes on the PR template

**Also useful:** [docs/compatibility-checklist.md](compatibility-checklist.md),
[docs/community-adapters.md](community-adapters.md) (when listing an adapter).

**Do not:** set `performance_claims_authorized=true`; write under
`fixtures/*/production/` without rights + volume; commit `runs/`,
`opencritique.db`, or `.env`.

**Issue templates:** Adapter proposal; Engineering workstream (F / E / etc.).

---

## Tier 3 — Schema, governance, rights, signing, claim gates

**In scope:** Frozen schema names, ADRs, trust store / signing policy, rights
clearance, milestone / §12 claim matrix, production authenticity evidence.

**Must read:**

1. Everything in Tier 2 that touches your area
2. [GOVERNANCE.md](../GOVERNANCE.md)
3. [SECURITY.md](../SECURITY.md)
4. [docs/REPOSITORY_PUBLICATION.md](REPOSITORY_PUBLICATION.md)
5. [docs/MILESTONES.md](MILESTONES.md) and
   [docs/v0.9-beta-go-no-go.md](v0.9-beta-go-no-go.md)
6. Relevant ADRs under `governance/decisions/`

**Hard rules:** No silent rename of frozen schema inventory; file an ADR for
normative policy. External-validity work on issues #3–#7 and related gates stays
blocked until real evidence lands — do not invent natural corpus or production
exports.

**Issue template:** Engineering workstream (B / G / H / etc.).

---

## Quick map

| Change type | Tier |
|---|---|
| Fix a typo in docs | 1 |
| Clarify Windows check path | 1 |
| New adapter stub + claims-locked test | 2 |
| Live runner plugin | 2 |
| Private pilot method report (claim-free) | 2 (Track B) |
| Schema field semantics | 3 |
| Unlock or reword claim authorization | 3 (expect rejection without gates) |
