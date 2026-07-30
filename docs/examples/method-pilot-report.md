# Private OpenCritique pilot report (template)

Fill this for lab-internal or public **method** reports. Expand from
[private-evaluation-pilot.md](../private-evaluation-pilot.md). Do not fill
evidence cells with fabricated IDs, natural counts, or production readiness.

**Non-claims:** `performance_claims_authorized=false`. This is not a leaderboard.
Sample fixtures and private `runs/` are not production authenticity. Private
metrics (if shown) are unauthorized and non-generalizable.

---

## 1. Scope and non-claims

| Field | Value |
|---|---|
| Pilot title | |
| Dates | |
| Lab / operator | |
| Manuscripts | Lab-owned / grant ids (no uncleared third-party text): |
| OpenCritique package version | |
| Schema freeze (`SCHEMA_FREEZE_RELEASE`) | |
| Adapter map / contract ids | |
| Upstream pins (if any) | |
| Evidence class used | `sample` / `private_live` / (production only if real MANIFEST) |

Explicit checkbox language for any published summary:

- [ ] We state `performance_claims_authorized=false`
- [ ] We do not present this pilot as a public reviewer ranking
- [ ] We label evidence class honestly (sample vs private_live vs production)

## 2. Protocol

### Review source

- [ ] Coarse live (`opencritique runners` / `pipeline coarse`) -> `runs/`
- [ ] OpenReviewer import (`--from-export` or HF-local) -> `runs/`
- [ ] Sample adapter path (software-only dry run)
- [ ] Other (describe):

### Convert -> evaluate -> scorecard

| Step | Command or note | Artifact path (under `runs/` or private store) |
|---|---|---|
| Convert | | |
| Evaluate | | |
| Scorecard | | |

### Optional adjudication

| Item | Notes |
|---|---|
| Studio / registry roles | |
| Blinding rules | |
| Conflict disclosure | |
| Cases claimed / submitted | |

## 3. Software / method observations

Descriptive infrastructure notes only — not reviewer-quality claims.

- Conversion loss, unresolved quotations, adapter friction:
-
- Matcher or scorecard behavior as infrastructure:
-
- Cross-adapter or schema friction:
-

## 4. Results boundary

| Item | Disclosure |
|---|---|
| Private metrics shown? | Yes / No — if yes, labeled unauthorized / non-generalizable |
| What was *not* measured | Natural corpus, independent auditors, holdout, … |

Do **not** reframe private numbers as public scientific validation.

## 5. Negative findings

| Blocker class | What blocked | What would be required |
|---|---|---|
| Rights | | |
| Volume / authentic exports | | |
| Staffing / experts | | |
| Calibration seeds | | |
| Matcher-audit natural n | | |
| Other | | |

Promotion toward production authenticity still requires evidence playbooks A–F
in [adapter-authenticity.md](../adapter-authenticity.md) — never auto-promote
`runs/` -> `fixtures/*/production/`.

## 6. Evidence not claimed

- [ ] No production `MANIFEST` ready status asserted from this pilot
- [ ] No natural matcher-audit DoD claimed unless real session manifests exist
- [ ] `python scripts/check_v09_gates.py` expected **NO-GO** until external evidence lands
- [ ] `performance_claims_authorized` remains **false**

## 7. What may be cited publicly (method only)

Allowed examples: schema/adapter configuration, conversion-loss software reports
(with evidence-class labels), pilot protocol (strata, blinding), negative
findings, links to public docs. See publish / do-not-publish in
[private-evaluation-pilot.md](../private-evaluation-pilot.md).

## Related

- [README examples index](README.md)
- [studio-walkthrough.md](studio-walkthrough.md)
- [MILESTONES.md](../MILESTONES.md)
- [v0.9-beta-go-no-go.md](../v0.9-beta-go-no-go.md)
