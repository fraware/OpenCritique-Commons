<div align="center">
  
<pre>
       
  ___                    ____      _ _   _                  
 / _ \ _ __   ___ _ __  / ___|_ __(_) |_(_) __ _ _   _  ___ 
| | | | '_ \ / _ \ '_ \| |   | '__| | __| |/ _` | | | |/ _ \
| |_| | |_) |  __/ | | | |___| |  | | |_| | (_| | |_| |  __/
 \___/| .__/ \___|_| |_|\____|_|  |_|\__|_|\__, |\__,_|\___|
  ____|_|                                     |_|           
 / ___|___  _ __ ___  _ __ ___   ___  _ __  ___             
| |   / _ \| '_ ` _ \| '_ ` _ \ / _ \| '_ \/ __|            
| |__| (_) | | | | | | | | | | | (_) | | | \__ \            
 \____\___/|_| |_| |_|_| |_| |_|\___/|_| |_|___/            
  
</pre>

</div>


<p align="center"><em>Infrastructure for scientific criticism you can inspect, challenge, and reproduce.</em></p>

<p align="center">
  <a href="https://github.com/fraware/OpenCritique-Commons/actions/workflows/ci.yml"><img src="https://github.com/fraware/OpenCritique-Commons/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License: Apache 2.0" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+" /></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/version-0.6.0a0-informational.svg" alt="Version 0.6.0a0" /></a>
  <a href="https://pypi.org/project/opencritique-commons/"><img src="https://img.shields.io/pypi/v/opencritique-commons.svg" alt="PyPI" /></a>
</p>

<p align="center"><strong>Scientific performance claims: NOT AUTHORIZED</strong>
(<code>performance_claims_authorized=false</code> until evidence gates in
<a href="docs/MILESTONES.md">docs/MILESTONES.md</a> are met. Not a quality badge.)</p>

---

## Why this exists

Automated tools can draft reviews in seconds. Science still needs criticism you can trace — from a manuscript passage, through a claim and its evidence, to adjudication and resolution.

OpenCritique Commons is open, system-neutral infrastructure for that chain. It helps researchers, tool builders, and reviewers share a common form for scientific concerns, keep human judgment in the loop, and evaluate systems without mistaking fixtures or preferences for evidence.

This is early work. It aims to be useful, honest, and welcoming to contributors.

## Get started (two equal tracks)

| | Track A — Tool builders | Track B — Scientists / labs |
|---|---|---|
| **Goal** | Map an upstream reviewer into shared schemas | Run inspectable private pilots without unlocking claims |
| **Start** | [START_HERE.md](START_HERE.md#track-a--adapter-author-tool-builders) | [START_HERE.md](START_HERE.md#track-b--scientist--lab-pilot) |
| **Depth** | [docs/adapter-authoring.md](docs/adapter-authoring.md) | [docs/private-evaluation-pilot.md](docs/private-evaluation-pilot.md) |

Both tracks share the same install and claim boundary. Full walkthrough:
[START_HERE.md](START_HERE.md).

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

**Install:** `pip install opencritique-commons` pulls alpha **`0.6.0a0`** from [PyPI](https://pypi.org/project/opencritique-commons/). Scientific performance claims remain **unauthorized**. For contributors, clone and `pip install -e ".[dev]"` (release path: [docs/release-pypi.md](docs/release-pypi.md)).

## Quick start

Python **3.12+** is required.

**From PyPI** (library consumers):

```bash
python -m pip install opencritique-commons
```

**From git** (contributors / editable install):

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

**One-shot demo (same path, offline):**
[`scripts/demo_adapter_path.sh`](scripts/demo_adapter_path.sh) or
[`scripts/demo_adapter_path.ps1`](scripts/demo_adapter_path.ps1)
(no paid APIs; prints `NOT AUTHORIZED`).

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
Fillable method report:
[docs/examples/method-pilot-report.md](docs/examples/method-pilot-report.md).
Sample Studio steps:
[docs/examples/studio-walkthrough.md](docs/examples/studio-walkthrough.md).
Promotion checklist (runs/ → production only via ingest after rights + volume):
[docs/adapter-authenticity.md](docs/adapter-authenticity.md#evidence-promotion-checklist).

## Works with OpenCritique

External tools can interoperate on **schemas and adapters** without implying
endorsement of reviewer quality. Compatibility means interchange contracts —
not calibrated scientific performance.

- [docs/compatibility-checklist.md](docs/compatibility-checklist.md) — what “OpenCritique-compatible” requires for interchange
- [docs/community-adapters.md](docs/community-adapters.md) — community adapter registry (in-tree and external)
- [docs/examples/adapter-integration-note.md](docs/examples/adapter-integration-note.md) — document an external adapter without quality claims
- [ADOPTERS.md](ADOPTERS.md) — organizations and tools using the commons (PR to add yourself)

## Operator entry points

| Path | Doc |
|---|---|
| Newcomer dual tracks | [START_HERE.md](START_HERE.md) |
| Claim-safe examples index | [docs/examples/README.md](docs/examples/README.md) |
| Offline adapter-path demo | [scripts/demo_adapter_path.sh](scripts/demo_adapter_path.sh) / [.ps1](scripts/demo_adapter_path.ps1) |
| Local Compose / Postgres / Studio | [docs/deployment-local.md](docs/deployment-local.md) |
| Bring-your-own-keys (BYOK) | [docs/deployment-byok.md](docs/deployment-byok.md) |
| OpenReviewer Space import (no GPU) | [docs/openreviewer-space-import.md](docs/openreviewer-space-import.md) |
| Private evaluation pilot (scientists) | [docs/private-evaluation-pilot.md](docs/private-evaluation-pilot.md) |
| Contributor roadmap themes | [docs/ROADMAP.md](docs/ROADMAP.md) |
| Outreach one-pager | [docs/outreach-one-pager.md](docs/outreach-one-pager.md) |
| Scorecard signing and trust store | [docs/signing-governance.md](docs/signing-governance.md) |
| Security / key compromise | [SECURITY.md](SECURITY.md) |
| Release checklist and claim gates | [docs/MILESTONES.md](docs/MILESTONES.md) |
| v0.9-beta go / no-go | [docs/v0.9-beta-go-no-go.md](docs/v0.9-beta-go-no-go.md) |
| Community norms | [docs/COMMUNITY.md](docs/COMMUNITY.md) |

## How to contribute

Contributions are welcome — code, docs, tests, adapters, and carefully sourced cases.

1. Start at [START_HERE.md](START_HERE.md) (Track A or Track B).
2. Read [CONTRIBUTING.md](CONTRIBUTING.md) and pick a tier in
   [docs/CONTRIBUTING_TIERS.md](docs/CONTRIBUTING_TIERS.md).
3. Follow the [Code of Conduct](CODE_OF_CONDUCT.md). Skim
   [GOVERNANCE.md](GOVERNANCE.md) and [SECURITY.md](SECURITY.md) only when
   changing process, APIs, or trust boundaries.
4. Open an issue or pull request with a clear scope and the checks you ran.

**Good first issues** (labeled
[`good first issue`](https://github.com/fraware/OpenCritique-Commons/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)):

- [#10](https://github.com/fraware/OpenCritique-Commons/issues/10) — newcomer walkthrough / START_HERE
- [#11](https://github.com/fraware/OpenCritique-Commons/issues/11) — hashing edge cases
- [#12](https://github.com/fraware/OpenCritique-Commons/issues/12) — starter engineering task

Also browse
[`help wanted`](https://github.com/fraware/OpenCritique-Commons/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22),
[`track-adapters`](https://github.com/fraware/OpenCritique-Commons/issues?q=is%3Aissue+is%3Aopen+label%3Atrack-adapters),
and
[`track-pilots`](https://github.com/fraware/OpenCritique-Commons/issues?q=is%3Aissue+is%3Aopen+label%3Atrack-pilots).

Good first areas:

- **Adapters** — map another reviewer system into the shared schemas (Track A)
- **Docs** — clarify concepts for newcomers
- **Tests and verifiers** — harden the contracts the rest of the project relies on
- **Pilots** — method reports and claim-free examples (Track B)
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

**Claims remain unauthorized.** We do not claim that any AI reviewer is accurate,
calibrated, or better than another. Synthetic fixtures exercise software
behavior. They do not establish scientific reliability.

Terminology used throughout the docs:

| Term | Meaning |
|---|---|
| **Sample conformance** | Maintainer-owned fixtures prove software contracts |
| **Production authenticity** | Rights-cleared upstream exports (issues #3 / #5) — not yet in tree |
| **Scientific performance claims** | Precision/recall, rankings, leaderboards — **unauthorized** (`performance_claims_authorized=false`) |

Production signing **public** keys are published under `trust/`; private keys stay offline. Natural manuscript import remains blocked pending affirmative rights clearance ([docs/rights-clearance-status.md](docs/rights-clearance-status.md)).

## License and citation

- Software: [Apache License 2.0](LICENSE)
- Cite the project with [CITATION.cff](CITATION.cff)
- Data (manuscripts, annotations, benchmark material) retains separate rights metadata

## Further reading

- [START_HERE.md](START_HERE.md) — dual-track newcomer walkthrough
- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, commits, and pull requests
- [docs/CONTRIBUTING_TIERS.md](docs/CONTRIBUTING_TIERS.md) — what to read by change class
- [docs/COMMUNITY.md](docs/COMMUNITY.md) — discussion norms and office hours
- [docs/MAINTAINERS.md](docs/MAINTAINERS.md) — triage SLA and claim-boundary review
- [ADOPTERS.md](ADOPTERS.md) — adopters table (PR welcome)
- [docs/ROADMAP.md](docs/ROADMAP.md) — contributor-facing themes mapped to milestones
- [docs/outreach-one-pager.md](docs/outreach-one-pager.md) — what OpenCritique is / is not
- [docs/examples/README.md](docs/examples/README.md) — claim-safe demos and templates index
- [docs/examples/method-pilot-report.md](docs/examples/method-pilot-report.md) — lab method / negative-finding template
- [docs/examples/studio-walkthrough.md](docs/examples/studio-walkthrough.md) — sample Studio adjudication steps
- [docs/examples/adapter-integration-note.md](docs/examples/adapter-integration-note.md) — external adapter write-up without quality claims
- [scripts/demo_adapter_path.sh](scripts/demo_adapter_path.sh) / [demo_adapter_path.ps1](scripts/demo_adapter_path.ps1) — offline Track A golden-path demo
- [docs/MILESTONES.md](docs/MILESTONES.md) — release checklist and claim gates
- [docs/private-evaluation-pilot.md](docs/private-evaluation-pilot.md) — private lab pilots; publish / do-not-publish boundary
- [docs/adapter-authenticity.md](docs/adapter-authenticity.md) — sample vs production fixtures; evidence promotion checklist
- [docs/adapter-authoring.md](docs/adapter-authoring.md) — third-adapter tutorial + skeleton
- [docs/compatibility-checklist.md](docs/compatibility-checklist.md) — external interchange checklist
- [docs/community-adapters.md](docs/community-adapters.md) — community adapter registry
- [docs/runner-plugins.md](docs/runner-plugins.md) — live runner plugin contract (`LiveRunnerPlugin`)
- [docs/deployment-byok.md](docs/deployment-byok.md) — BYOK credential gate + Coarse live runner
- [docs/openreviewer-space-import.md](docs/openreviewer-space-import.md) — OpenReviewer Space → `--from-export`
- [docs/rights-memorandum.md](docs/rights-memorandum.md) — external import rules
- [GOVERNANCE.md](GOVERNANCE.md) — how decisions are made
- [SECURITY.md](SECURITY.md) — how to report vulnerabilities
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — community expectations
- [docs/REPOSITORY_PUBLICATION.md](docs/REPOSITORY_PUBLICATION.md) — publication integrity boundary
