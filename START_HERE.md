# Start here

OpenCritique Commons is open infrastructure for scientific criticism you can
inspect, challenge, and reproduce — schemas, adapters, evaluation, adjudication,
and claim-locked scorecards. It is **not** a reviewer leaderboard.

This page is the short path in. Pick one track (both are first-class). Expect
about **30 minutes** on a clean clone after install.

**Shared rules before you start**

- Participation follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- Scientific performance claims stay unauthorized
  (`performance_claims_authorized=false`) until evidence gates in
  [docs/MILESTONES.md](docs/MILESTONES.md) are met. Do not invent production
  MANIFESTs, natural counts, or claim unlocks.
- Prefer a linked issue. Open [good first issues](https://github.com/fraware/OpenCritique-Commons/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
  include [#11](https://github.com/fraware/OpenCritique-Commons/issues/11),
  [#12](https://github.com/fraware/OpenCritique-Commons/issues/12),
  and newer labeled starters such as
  [#24](https://github.com/fraware/OpenCritique-Commons/issues/24)–[#30](https://github.com/fraware/OpenCritique-Commons/issues/30).

**Claim-boundary checkbox (copy into your PR or issue):**

- [ ] This work does **not** authorize precision/recall/comparative reviewer-quality claims.
- [ ] Sample fixtures and private `runs/` are not treated as production authenticity.

---

## 5-minute overview

| Package area | Role |
|---|---|
| Schemas | Shared shapes for concerns, evidence, adjudication, resolution |
| Adapters | Bridges from external reviewer systems into those schemas |
| Evaluation | Matching, scoring, signed scorecards (claims locked) |
| Registry / Studio | Artifact storage, rights, human adjudication |
| Runners (optional) | Live Coarse / OpenReviewer → private `runs/` only |

**Version identity:** package **`0.6.0a0`**; frozen schema inventory **`0.5.0a1`**.

Install once (both tracks):

```bash
git clone https://github.com/fraware/OpenCritique-Commons.git
cd OpenCritique-Commons

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

bash scripts/check.sh              # Windows: Git Bash/WSL, or run ruff / pyright / pytest piecewise
```

On Windows without bash: `ruff check src tests scripts`, then `pyright`, then
`pytest`. Details: [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Track A — Adapter author (tool builders)

Goal: add or extend an upstream bridge into the shared schemas without shipping
fake production authenticity.

### A1. Confirm the tree is healthy

```bash
python -m pip install -e ".[dev]"
bash scripts/check.sh
```

### A2. Copy the adapter skeleton

Copy [`templates/adapter-skeleton/`](templates/adapter-skeleton/) and rename
placeholders (`example` → your slug). Follow
[docs/adapter-authoring.md](docs/adapter-authoring.md).

### A3. Smoke convert (sample path)

After wiring convert (in-tree Coarse example):

```bash
opencritique adapters coarse \
  --manifest benchmarks/coarse-synth-v0.1/manifest.json \
  --benchmark-root benchmarks/coarse-synth-v0.1 \
  --mapping fixtures/coarse/maps/synth-map.json \
  --output coarse-submission.json
```

Generic shape for a new slug:

```bash
opencritique adapters <slug> \
  --manifest benchmarks/<bench>/manifest.json \
  --benchmark-root benchmarks/<bench> \
  --mapping fixtures/<slug>/maps/synth-map.json \
  --output <slug>-submission.json
```

Then evaluation / scorecard as in the [README golden path](README.md#golden-path-sample-vision).
Expect claim authorization printed as `NOT AUTHORIZED`.

**One-shot offline demo** (same convert → eval → scorecard; no paid APIs):

```bash
bash scripts/demo_adapter_path.sh
# Windows PowerShell: .\scripts\demo_adapter_path.ps1
```

When documenting an external adapter without quality claims, use
[docs/examples/adapter-integration-note.md](docs/examples/adapter-integration-note.md).

### A4. Optional second step — live runner plugin

If the upstream can run locally or via BYOK, read
[docs/runner-plugins.md](docs/runner-plugins.md). Live outputs stay under
`runs/`; the CLI refuses `fixtures/*/production/` writes.

### A5. Exit criteria

Open a PR that:

1. Adds a sample adapter stub (from the skeleton) or improves an existing map.
2. Includes a claims-locked test (`performance_claims_authorized=false`).
3. Does **not** invent production `MANIFEST` readiness or unlock §12 claims.

Before opening: skim [docs/CONTRIBUTING_TIERS.md](docs/CONTRIBUTING_TIERS.md)
(adapters tier), [docs/compatibility-checklist.md](docs/compatibility-checklist.md),
and the claim checkboxes above. Run
`python scripts/check_adapter_compatibility.py` on your adapter path (see
[docs/community-adapters.md](docs/community-adapters.md)).

---

## Track B — Scientist / lab pilot

Goal: run convert → evaluate → scorecard → optional Studio on sample fixtures
(and optionally rights-owned private material) without treating results as
authorized scientific performance.

### B1. Same install

```bash
python -m pip install -e ".[dev]"
bash scripts/check.sh
```

### B2. Golden path (sample conformance)

```bash
opencritique adapters coarse \
  --manifest benchmarks/coarse-synth-v0.1/manifest.json \
  --benchmark-root benchmarks/coarse-synth-v0.1 \
  --mapping fixtures/coarse/maps/synth-map.json \
  --output coarse-submission.json

opencritique evaluation run \
  --manifest benchmarks/coarse-synth-v0.1/manifest.json \
  --benchmark-root benchmarks/coarse-synth-v0.1 \
  --submission coarse-submission.json \
  --output evaluation-result.json

opencritique evaluation scorecard \
  --result evaluation-result.json \
  --json-output scorecard.json
```

Expect `NOT AUTHORIZED`. Then sample Studio:

```bash
opencritique-registry bootstrap-sample-workspace
opencritique-registry serve
```

Open `http://127.0.0.1:8000/studio`, paste the adjudicator token from bootstrap,
**Connect** → **Claim adjudication** → inspect REF-01 → submit.

Step-by-step Studio notes:
[docs/examples/studio-walkthrough.md](docs/examples/studio-walkthrough.md).

### B3. Publish / do-not-publish boundary

Read [docs/private-evaluation-pilot.md](docs/private-evaluation-pilot.md).
Private `runs/` are not production authenticity. Do not publish precision/recall
or rankings as authorized scientific results. Fillable method / negative-finding
template: [docs/examples/method-pilot-report.md](docs/examples/method-pilot-report.md).

### B4. Optional live Coarse / OpenReviewer under `runs/`

```bash
# Live Coarse (BYOK) → private runs/
pip install -e ".[live-coarse]"
opencritique runners pipeline coarse \
  --manuscript corpus/samples/sample-econ-01/manuscript.md \
  --out-dir runs/pipeline/coarse-sample-econ-01

# OpenReviewer import (no GPU / no OpenAI key)
opencritique runners openreviewer \
  --from-export path/to/space-or-local-export.json \
  --output runs/openreviewer/export.json
```

Lab-owned papers only for real pilots; never commit secrets or uncleared text.
Outputs stamp `evidence_class=private_live` and claims locked.

### B5. Exit criteria

Draft a private pilot / negative-finding report using
[docs/examples/method-pilot-report.md](docs/examples/method-pilot-report.md)
(or the outline in
[docs/private-evaluation-pilot.md](docs/private-evaluation-pilot.md#negative-finding--pilot-report-outline)).
No claim unlock. `python scripts/check_v09_gates.py` should remain NO-GO until
real external evidence lands.

---

## What to read next

| If you are… | Read |
|---|---|
| New to the repo | This file, then [docs/CONTRIBUTING_TIERS.md](docs/CONTRIBUTING_TIERS.md) |
| Want claim-safe demos / templates | [docs/examples/README.md](docs/examples/README.md) |
| Track A write-up | [docs/examples/adapter-integration-note.md](docs/examples/adapter-integration-note.md) |
| Track A compatibility | [docs/compatibility-checklist.md](docs/compatibility-checklist.md), [docs/community-adapters.md](docs/community-adapters.md) |
| Track B method report | [docs/examples/method-pilot-report.md](docs/examples/method-pilot-report.md) |
| Joining discussion | [docs/COMMUNITY.md](docs/COMMUNITY.md) |
| Maintainer triage | [docs/MAINTAINERS.md](docs/MAINTAINERS.md) |
| Changing code or docs | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Roadmap / outreach | [docs/ROADMAP.md](docs/ROADMAP.md), [docs/outreach-one-pager.md](docs/outreach-one-pager.md) |
| Listing an adopter | [ADOPTERS.md](ADOPTERS.md) |
| Checking honesty gates | [docs/MILESTONES.md](docs/MILESTONES.md) |
| Reporting a vulnerability | [SECURITY.md](SECURITY.md) |
