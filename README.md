<div align="center">
  
<pre>
  
   ___                    ____      _ _   _                  
  / _ \ _ __   ___ _ __  / ___|_ __(_) |_(_) __ _ _   _  ___ 
 | | | | '_ \ / _ \ '_ \| |   | '__| | __| |/ _` | | | |/ _ \
 | |_| | |_) |  __/ | | | |___| |  | | |_| | (_| | |_| |  __/
  \___/| .__/ \___|_| |_|\____|_|  |_|\__|_|\__, |\__,_|\___|
  / ___|_|_  _ __ ___  _ __ ___   ___  _ __  __|_|           
 | |   / _ \| '_ ` _ \| '_ ` _ \ / _ \| '_ \/ __|            
 | |__| (_) | | | | | | | | | | | (_) | | | \__ \            
  \____\___/|_| |_| |_|_| |_| |_|\___/|_| |_|___/      
  
</pre>

</div>

<p align="center"><em>Infrastructure for scientific criticism you can inspect, challenge, and reproduce.</em></p>

---

## Why this exists

Automated tools can draft reviews in seconds. Science still needs criticism you can trace — from a manuscript passage, through a claim and its evidence, to adjudication and resolution.

OpenCritique Commons is open, system-neutral infrastructure for that chain. It helps researchers, tool builders, and reviewers share a common form for scientific concerns, keep human judgment in the loop, and evaluate systems without mistaking fixtures or preferences for evidence.

This is early work. It aims to be useful, honest, and welcoming to contributors.

## What you will find

| Package | Role |
|---|---|
| `opencritique_schema` | Shared shapes for concerns, evidence, adjudication, and resolution |
| `opencritique_registry` | Artifact storage, rights controls, and expert adjudication workflows |
| `opencritique_evaluation` | Matching, scoring, sensitivity checks, and signed scorecards |
| `opencritique_adapters` | Bridges from external reviewer systems into the shared schemas |
| `opencritique_acquisition` | Records for bringing external sources in with rights in mind |
| `opencritique_ingestion` | Markdown/LaTeX/PDF → document graph |
| `opencritique_verification` | Deterministic table, citation, and Python verifiers |
| `opencritique_runners` | Optional live Coarse / OpenReviewer runners (`opencritique runners`) |

The repo also includes schemas, fixtures, synthetic benchmark cases, docs, and tests — enough to develop against today.

**Version identity:** package/engineering release **`0.6.0a0`**; frozen schema inventory remains **`0.5.0a1`** (`SCHEMA_FREEZE_RELEASE`). See [docs/MILESTONES.md](docs/MILESTONES.md).

## Quick start

Python **3.12+** is required.

```bash
git clone https://github.com/fraware/OpenCritique-Commons.git
cd OpenCritique-Commons

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

bash scripts/check.sh              # lint, types, and tests
```

On Windows, Git Bash or WSL works well for `scripts/check.sh`. After the editable install you can also run `ruff`, `pyright`, and `pytest` directly.

## Two operator tracks

| Track | What it proves | What you need | What it does **not** unlock |
|---|---|---|---|
| **Sample conformance** (offline) | Software contracts: convert → evaluate → scorecard → Studio | `pip install -e ".[dev]"` + in-tree fixtures | Production authenticity; scientific claims |
| **Live upstream runners** (optional) | Operator-local reviews from real Coarse / OpenReviewer tooling under `runs/` | See install + CLI below | Production `MANIFEST` `ready`; `performance_claims_authorized` |

**BYOK truthfulness:** `OPENCRITIQUE_BYOK_API_KEY` (or `OPENAI_API_KEY` alias) is a **credential gate** for registry BYOK mode **and** the Coarse live runner. It is **not** an OpenReviewer backend and **not** a claim-authorization switch. Private `runs/` ≠ rights-cleared production fixtures (issues #3 / #5). Claims stay **NOT AUTHORIZED**. See [docs/adapter-authenticity.md](docs/adapter-authenticity.md) and [docs/deployment-byok.md](docs/deployment-byok.md).

### Live extras and CLI

```bash
# Coarse (BYO-key via OpenAI / OpenRouter-style models; pins coarse-ink==1.8.0)
pip install -e ".[live-coarse]"

# OpenReviewer HF local (GPU recommended; does not use OpenAI/BYOK keys)
pip install -e ".[live-openreviewer]"
```

Never commit `.env`. Prefer `OPENCRITIQUE_BYOK_API_KEY` + optional
`OPENCRITIQUE_BYOK_PROVIDER_ID`; if unset, `OPENAI_API_KEY` aliases for Coarse.
Rotate any key that was exposed.

```bash
# Live Coarse review → runs/ (refuses fixtures/*/production/)
opencritique runners coarse \
  --manuscript corpus/samples/sample-econ-01/manuscript.md \
  --output runs/coarse/sample-econ-01.json

# Live Coarse → convert → eval/scorecard when sample gold exists
opencritique runners pipeline coarse \
  --manuscript corpus/samples/sample-econ-01/manuscript.md \
  --out-dir runs/pipeline/coarse-sample-econ-01

# Register private live export → Studio claimable tasks
opencritique-registry import-live-run \
  --from runs/pipeline/coarse-sample-econ-01 \
  --manuscript corpus/samples/sample-econ-01/manuscript.md

# Demo wrappers (call paid APIs; not for default CI; exit + artifact checklist)
#   scripts/live_pipeline_demo.sh
#   scripts/live_pipeline_demo.ps1
```

### OpenReviewer import (no GPU) or HF local

```bash
# Prefer import: HF Space or local OpenReviewer export (no OpenAI key, no GPU)
opencritique runners openreviewer \
  --from-export path/to/space-or-local-export.json \
  --output runs/openreviewer/export.json

# Optional HF local when [live-openreviewer] is installed (GPU; --allow-cpu override)
# opencritique runners openreviewer --manuscript path/to/paper.md \
#   --output runs/openreviewer/hf-local.json
```

**Blunt:** OpenAI/BYOK keys do not run OpenReviewer. Cookbook:
[docs/openreviewer-space-import.md](docs/openreviewer-space-import.md).

Outputs stamp `evidence_class=private_live` and
`performance_claims_authorized=false`. The CLI refuses to write under
`fixtures/*/production/`. Live runs do **not** move
`python scripts/check_v09_gates.py` to GO.
## Golden path (sample vision)

Complete this walkthrough in under 30 minutes to exercise the sample
conformance vision end-to-end. This path uses maintainer-owned fixtures only.

**Non-claims:** sample fixtures ≠ production authenticity ≠ scientific
performance. Scorecards stay `NOT AUTHORIZED`
(`performance_claims_authorized=false`).

### 1. Install and check

```bash
python -m pip install -e ".[dev]"
bash scripts/check.sh
```

### 2. Synthetic Coarse convert → evaluate → scorecard

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

Expect claim authorization printed as `NOT AUTHORIZED`.

### 3. Sample Studio adjudication

```bash
# Local SQLite (or point --database-url at Compose Postgres)
opencritique-registry bootstrap-sample-workspace
opencritique-registry serve
```

Open `http://127.0.0.1:8000/studio`, paste the **adjudicator** token printed by
bootstrap, click **Connect**, then **Claim adjudication**, inspect REF-01, and
submit. Compose users: see [docs/deployment-local.md](docs/deployment-local.md)
(`docker compose up --build` migrates automatically, then run bootstrap against
Postgres).

## For scientists

OpenCritique Commons is **method tooling** for inspectable criticism workflows —
schemas, adapters, evaluation, adjudication, and claim-locked scorecards. It is
**not** a public reviewer leaderboard.

| You can | You must not |
|---|---|
| Run private pilots on **rights-owned** papers (`runs/`, lab grant on file) | Publish precision/recall or rankings as authorized scientific results |
| Cite conversion loss, protocols, and limitations honestly | Equate sample fixtures or private live exports with production authenticity |
| Follow evidence playbooks A–F when real rights/exports/experts arrive | Fabricate MANIFESTs, natural counts, or set `performance_claims_authorized=true` |

**Cite limitations:** state package/schema versions; label evidence class
(sample / private_live / production); keep §12 claims unauthorized; point
readers at [docs/MILESTONES.md](docs/MILESTONES.md) and
`python scripts/check_v09_gates.py` (fail-closed NO-GO until evidence lands).

Pilot kit + negative-finding report outline:
[docs/private-evaluation-pilot.md](docs/private-evaluation-pilot.md).
Promotion checklist (runs/ → production only via ingest after rights + volume):
[docs/adapter-authenticity.md](docs/adapter-authenticity.md#evidence-promotion-checklist).

## Operator entry points

| Path | Doc |
|---|---|
| Local Compose / Postgres / Studio | [docs/deployment-local.md](docs/deployment-local.md) |
| Bring-your-own-keys (BYOK) | [docs/deployment-byok.md](docs/deployment-byok.md) |
| OpenReviewer Space import (no GPU) | [docs/openreviewer-space-import.md](docs/openreviewer-space-import.md) |
| Private evaluation pilot (scientists) | [docs/private-evaluation-pilot.md](docs/private-evaluation-pilot.md) |
| Scorecard signing and trust store | [docs/signing-governance.md](docs/signing-governance.md) |
| Security / key compromise | [SECURITY.md](SECURITY.md) |
| Release checklist and claim gates | [docs/MILESTONES.md](docs/MILESTONES.md) |
| v0.9-beta go / no-go | [docs/v0.9-beta-go-no-go.md](docs/v0.9-beta-go-no-go.md) |

## How to contribute

Contributions are welcome — code, docs, tests, adapters, and carefully sourced cases.

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
2. Skim [GOVERNANCE.md](GOVERNANCE.md) and [SECURITY.md](SECURITY.md) if you are changing process, APIs, or trust boundaries.
3. Open an issue or pull request with a clear scope and the checks you ran.

Good first areas:

- **Adapters** — map another reviewer system into the shared schemas
- **Docs** — clarify concepts for newcomers
- **Tests and verifiers** — harden the contracts the rest of the project relies on
- **Cases** — add or refine examples with care for rights and provenance

Not sure where to start? Open an issue and say what you enjoy working on. We would rather help you find a fit than lose a contributor to setup friction.

## What we care about

- **Evidence** — criticism should point at something real in the manuscript or record
- **Uncertainty** — confidence and disagreement belong in the model, not only in footnotes
- **Fairness** — adjudication should be inspectable; preferences should not hide as metrics
- **Rights** — manuscripts, annotations, and cases carry their own permissions
- **Reproducibility** — schemas, runs, and scorecards should be checkable by others

## Status

This repository is **early infrastructure**. Packages, schemas, and fixtures exist so people can build and test together.

Terminology used throughout the docs:

| Term | Meaning |
|---|---|
| **Sample conformance** | Maintainer-owned fixtures prove software contracts |
| **Production authenticity** | Rights-cleared upstream exports (issues #3 / #5) — not yet in tree |
| **Scientific performance claims** | Precision/recall, rankings, leaderboards — **unauthorized** (`performance_claims_authorized=false`) |

We are **not** claiming that any AI reviewer is accurate, calibrated, or better than another. Synthetic fixtures exercise software behavior. They do not establish scientific reliability. Production signing **public** keys are published under `trust/`; private keys stay offline. Natural manuscript import remains blocked pending affirmative rights clearance ([docs/rights-clearance-status.md](docs/rights-clearance-status.md)).

## License and citation

- Software: [Apache License 2.0](LICENSE)
- Cite the project with [CITATION.cff](CITATION.cff)
- Data (manuscripts, annotations, benchmark material) retains separate rights metadata

## Further reading

- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, commits, and pull requests
- [docs/MILESTONES.md](docs/MILESTONES.md) — release checklist and claim gates
- [docs/private-evaluation-pilot.md](docs/private-evaluation-pilot.md) — private lab pilots; publish / do-not-publish boundary
- [docs/adapter-authenticity.md](docs/adapter-authenticity.md) — sample vs production fixtures; evidence promotion checklist
- [docs/adapter-authoring.md](docs/adapter-authoring.md) — third-adapter tutorial + skeleton
- [docs/runner-plugins.md](docs/runner-plugins.md) — live runner plugin contract (`LiveRunnerPlugin`)
- [docs/deployment-byok.md](docs/deployment-byok.md) — BYOK credential gate + Coarse live runner
- [docs/openreviewer-space-import.md](docs/openreviewer-space-import.md) — OpenReviewer Space → `--from-export`
- [docs/rights-memorandum.md](docs/rights-memorandum.md) — external import rules
- [GOVERNANCE.md](GOVERNANCE.md) — how decisions are made
- [SECURITY.md](SECURITY.md) — how to report vulnerabilities
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — community expectations
- [docs/REPOSITORY_PUBLICATION.md](docs/REPOSITORY_PUBLICATION.md) — publication integrity boundary
