# OpenCritique Commons — outreach one-pager

Neutral coordination layer for scientific critique: schemas, adapters, runners,
signed scorecards, and rights-aware adjudication. Closed reviewer tools may
still exist; shared formats and evidence trails live here.

**Claims:** scientific performance claims are **not authorized**
(`performance_claims_authorized=false`) until public gates are met with real
evidence. Compatibility is interchange, not quality endorsement.

## What it is

- An open interoperability layer for critique workflows (convert, evaluate,
  scorecard, optional Studio adjudication)
- Frozen schemas and sample-conformance adapters (e.g. Coarse, OpenReviewer
  sample paths)
- Operator-local private pilots on **rights-owned** manuscripts (`runs/`)
- Honest milestone and gate tracking ([MILESTONES.md](MILESTONES.md))

## What it is not

- A public AI-reviewer leaderboard or ranking product
- A black-box replacement for peer review
- Authorization to publish precision/recall as scientific results today
- Auto-promotion of private `runs/` into production authenticity fixtures
- An endorsement that any upstream tool is "correct" or "better"

## For journals and venues

| Useful for | Not for |
|---|---|
| Discussing inspectable critique protocols and evidence trails | Mandating a proprietary reviewer vendor |
| Citing schema / method limitations honestly | Treating sample demos as production validation |
| Pointing authors/labs at claim-locked scorecards | Publishing venue leaderboards from unauthorized metrics |

Contact path: GitHub issues / discussions; see [COMMUNITY.md](COMMUNITY.md).

## For labs and scientists

| Useful for | Not for |
|---|---|
| Private pilots on rights-owned papers | Uncleared third-party corpus scraping |
| Method reports (conversion loss, protocol, negative findings) | Marketing unauthorized performance numbers |
| Sample Studio walkthroughs and offline demos | Equating sample fixtures with natural adjudicated evidence |

Start: [private-evaluation-pilot.md](private-evaluation-pilot.md) and
[examples/method-pilot-report.md](examples/method-pilot-report.md).

## For tool authors

| Useful for | Not for |
|---|---|
| Bridging upstream exports into OpenCritique submissions | Claiming production authenticity without rights + volume |
| Listing in the community adapters registry after checklist | Framing compatibility as reviewer-quality certification |
| Optional live runners that refuse production fixture paths | Setting `performance_claims_authorized=true` |

Start: [adapter-authoring.md](adapter-authoring.md),
[compatibility-checklist.md](compatibility-checklist.md),
[examples/adapter-integration-note.md](examples/adapter-integration-note.md),
offline demo [`scripts/demo_adapter_path.sh`](../scripts/demo_adapter_path.sh).

## Proof without claim unlock

- Offline demo: synthetic Coarse convert -> eval -> scorecard (`NOT AUTHORIZED`)
- Templates under [examples/README.md](examples/README.md)
- Adopter listings: [ADOPTERS.md](../ADOPTERS.md) (usage, not endorsement)
- Roadmap themes: [ROADMAP.md](ROADMAP.md)

## One sentence to reuse

OpenCritique Commons is the open interoperability layer for scientific critique
workflows — schemas, adapters, and claim-locked scorecards — not a reviewer
leaderboard and not a license to publish unauthorized performance claims.
