# Private evaluation pilot kit

How a lab runs OpenCritique Commons on **rights-owned** papers privately —
without treating local metrics as public scientific claims, and without
promoting private `runs/` into production authenticity.

This is **method tooling**, not a leaderboard. Sample fixtures and private live
exports do not authorize precision/recall marketing or comparative reviewer
rankings. Keep `performance_claims_authorized=false`.

## Who this is for

Researchers and labs that:

- Own (or have written grant for) the manuscripts they will evaluate
- Want convert → evaluate → scorecard → optional Studio adjudication on their material
- Need a clear publish / do-not-publish boundary while public commons gates stay NO-GO

## Preconditions

| Requirement | Notes |
|---|---|
| Rights | Lab-owned papers or affirmative written grant (see [rights-memorandum.md](rights-memorandum.md)). Do not embed uncleared third-party text. |
| Install | `pip install -e ".[dev]"`; for live Coarse add `.[live-coarse]`; OpenReviewer import needs no OpenAI key |
| Honesty | Scorecards and live provenance stamp claims **unauthorized**; do not reframe private numbers as public validation |

Negative rights findings alone do **not** unlock natural import into the public
corpus (issue #7). Private pilots stay under operator-local paths.

## Private pilot loop (executable outline)

```text
1. Rights-owned manuscript (lab grant on file)
2. Review export
     ├─ Coarse live:  opencritique runners coarse / pipeline coarse  → runs/
     ├─ OpenReviewer: --from-export (Space/local) or HF-local         → runs/
     └─ Or sample adapter path for software-only dry runs
3. Convert / evaluate / scorecard (private artifacts)
4. Optional: registry + Studio adjudication on lab-owned cases
5. Document methods, conversion loss, and limitations
6. Do NOT auto-promote runs/ → fixtures/*/production/
```

### Suggested commands (operator-local)

```bash
# Live Coarse (BYOK) → private runs/
pip install -e ".[live-coarse]"
opencritique runners pipeline coarse \
  --manuscript path/to/lab-owned-paper.md \
  --out-dir runs/pipeline/lab-pilot-01

# OpenReviewer import (no GPU / no OpenAI key)
opencritique runners openreviewer \
  --from-export path/to/space-or-local-export.json \
  --output runs/openreviewer/lab-pilot-01.json
```

Outputs under `runs/` stamp `evidence_class=private_live` and
`performance_claims_authorized=false`. The CLI refuses to write under
`fixtures/*/production/`. See [deployment-byok.md](deployment-byok.md) and the
README live-upstream track.

Studio / registry on lab-owned material: follow sample bootstrap patterns in
[deployment-local.md](deployment-local.md), using only rights-cleared cases.
Paid expert workflows remain blocked until rates and natural calibration slots
are filled — see [expert-program-ops.md](expert-program-ops.md).

## What may be published

Labs may publish **descriptive method and protocol** material, for example:

- How OpenCritique schemas, adapters, and evaluation were configured
- Conversion-loss / cross-adapter **software** reports (explicitly labeled sample
  vs private vs production when applicable)
- Pilot protocol: strata, blinding rules, adjudication instructions
- Negative findings: what failed, what remained blocked, what evidence is still
  missing for public authenticity
- Links to public docs: matcher-audit protocol, expert ops, authenticity playbook

Always disclose that private pilot metrics are **not** authorized scientific
performance claims and are **not** a public leaderboard.

## What must not be published (as claims)

- Precision / recall / severity-weighted metrics framed as scientific results
- Comparative reviewer rankings or “system X beats Y” marketing
- Language that equates sample fixtures or private `runs/` with production
  authenticity (issues #3 / #5)
- Invented production `MANIFEST` readiness, fabricated natural decision counts,
  or fake adjudicator / staffing IDs
- Enabling or asserting `performance_claims_authorized=true`

Public commons promotion path (rights + volume + ingest stage only):
[adapter-authenticity.md](adapter-authenticity.md#evidence-promotion-checklist).

## Linked protocols

| Topic | Doc |
|---|---|
| Sample vs production; runs/ promotion | [adapter-authenticity.md](adapter-authenticity.md) |
| Matcher-audit pilot protocol | [matcher-audit-protocol.md](matcher-audit-protocol.md) |
| Matcher-audit denominators / natural DoD | [matcher-audit-denominators.md](matcher-audit-denominators.md) |
| Natural session layout | [../corpus/matcher-audit/README.md](../corpus/matcher-audit/README.md) |
| Expert ops / calibration fail-closed | [expert-program-ops.md](expert-program-ops.md) |
| Compensation terms | [expert-compensation-terms.md](expert-compensation-terms.md) |
| v0.9 gates (stay NO-GO without evidence) | [v0.9-beta-go-no-go.md](v0.9-beta-go-no-go.md) |
| Milestone / §12 claim matrix | [MILESTONES.md](MILESTONES.md) |
| Fillable method report | [examples/method-pilot-report.md](examples/method-pilot-report.md) |
| Examples index / demos | [examples/README.md](examples/README.md) |
| Contributor roadmap themes | [ROADMAP.md](ROADMAP.md) |
| Outreach one-pager | [outreach-one-pager.md](outreach-one-pager.md) |

## Negative-finding / pilot report outline

Use this template for lab-internal or public **method** reports. Do not fill
evidence cells with fabricated IDs or counts. A fillable copy lives at
[examples/method-pilot-report.md](examples/method-pilot-report.md); Studio sample
steps at [examples/studio-walkthrough.md](examples/studio-walkthrough.md).

```markdown
# Private OpenCritique pilot report

## 1. Scope and non-claims
- Manuscripts: lab-owned / grant ids (no uncleared third-party text)
- Tools/versions: OpenCritique package, adapter map ids, upstream pins if any
- Explicit: performance_claims_authorized=false; not a leaderboard

## 2. Protocol
- Review source (Coarse live / OpenReviewer import / other)
- Convert → evaluate → scorecard steps and artifact paths (under runs/ or private store)
- Optional adjudication: Studio roles, blinding, conflict disclosure

## 3. Software / method observations
- Conversion loss, unresolved quotations, adapter friction
- Matcher or scorecard behavior as infrastructure (descriptive only)

## 4. Results boundary
- Private metrics (if shown): labeled unauthorized / non-generalizable
- What was *not* measured (natural corpus, independent auditors, holdout)

## 5. Negative findings
- Blockers (rights, volume, staffing, calibration seeds, matcher-audit natural n)
- What would be required to promote toward production authenticity (A–F)

## 6. Evidence not claimed
- No production MANIFEST ready status asserted from this pilot
- No natural matcher-audit DoD met unless real session manifests exist
- Gates: `python scripts/check_v09_gates.py` expected NO-GO until external evidence lands
```

## Gate honesty

`python scripts/check_v09_gates.py` remains fail-closed: missing or blocked
evidence artifacts → non-zero exit (NO-GO). Private pilots do not change that.
The script never invents natural counts and never sets
`performance_claims_authorized=true`.
