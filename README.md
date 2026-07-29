```text
             ____                   ______     _ __  _
            / __ \____  ___  ____  / ____/____(_) /_(_)___ ___  _____
           / / / / __ \/ _ \/ __ \/ /   / ___/ / __/ / __ `/ / / / _ \
          / /_/ / /_/ /  __/ / / / /___/ /  / / /_/ / /_/ / /_/ /  __/
          \____/ .___/\___/_/ /_/\____/_/  /_/\__/_/\__, /\__,_/\___/
              /_/                                     /_/

                 ______
                / ____/___  ____ ___  ____ ___  ____  ____  _____
               / /   / __ \/ __ `__ \/ __ `__ \/ __ \/ __ \/ ___/
              / /___/ /_/ / / / / / / / / / / / /_/ / / / (__  )
              \____/\____/_/ /_/_/ /_/ /_/_/ /_/\____/_/ /_/____/
```

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

## Operator entry points

| Path | Doc |
|---|---|
| Local Compose / Postgres / Studio | [docs/deployment-local.md](docs/deployment-local.md) |
| Bring-your-own-keys (BYOK) | [docs/deployment-byok.md](docs/deployment-byok.md) |
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
- [docs/adapter-authenticity.md](docs/adapter-authenticity.md) — sample vs production fixtures
- [docs/rights-memorandum.md](docs/rights-memorandum.md) — external import rules
- [GOVERNANCE.md](GOVERNANCE.md) — how decisions are made
- [SECURITY.md](SECURITY.md) — how to report vulnerabilities
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — community expectations
- [docs/REPOSITORY_PUBLICATION.md](docs/REPOSITORY_PUBLICATION.md) — publication integrity boundary
