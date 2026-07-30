# Contributor roadmap

Contributor-facing themes mapped to [MILESTONES.md](MILESTONES.md). This page
does **not** invent GO status, unlock §12 claims, or fabricate authenticity
evidence. Gate truth lives in MILESTONES and `scripts/check_v09_gates.py`.

**Claims posture:** scientific performance claims stay **unauthorized** until
the claim-authorization matrix and v0.9 / v1.0 evidence gates are satisfied.

## Themes -> milestones

| Theme | What contributors can do now | Milestone anchor | Status note (from MILESTONES) |
|---|---|---|---|
| Schema / interchange freeze | Consume frozen schemas; cite `SCHEMA_FREEZE_RELEASE` | 0–1 (`v0.5.0a1` / kernel) | Schema freeze pinned; engineering surface on `main` |
| Sample adapters and conformance | Author sample adapters; offline convert -> eval -> scorecard | 1–2 | Sample Coarse / OpenReviewer paths present; production exports blocked (#3 / #5) |
| Compatibility and registry | Follow compatibility checklist; PR community-adapters listing | 2 (ecosystem surface) | Compatibility != quality endorsement |
| Runner plugins | Optional live runners under `runs/`; refuse production fixture writes | Engineering depth (not v0.9 DoD) | Private live != production authenticity |
| Private lab pilots | Rights-owned method reports; publish/do-not-publish boundary | 3 (sample maturity) | Method tooling only; no leaderboard |
| Studio / adjudication UX | Sample bootstrap walkthrough; docs and UX polish | 3 | Sample conformance; paid natural pilots pending |
| Authenticity / v0.9 evidence | Help only with **real** evidence playbooks A–F; never invent counts | 4 (`v0.9-beta`) | **NO-GO** until `check_v09_gates.py` exits 0 |
| Deferred product depth | Verifiers, docs, specs (#16–#19); no hosted SaaS requirement | Beyond current GO | Specs only; community can help verifiers/docs |

## Dual release-note lanes (when cutting notes)

Use separate sections so engineering progress is not misread as science:

1. **Engineering** — runtime, CLI, CI, deploy runbooks
2. **Adapters** — sample/external interchange, loss reports, registry listings
3. **Docs and pilots** — method templates, walkthroughs, pilot kit updates

Never write "accuracy improved" or leaderboard language without claim gates.

## Where to start

| Track | Entry |
|---|---|
| Tool builders | [adapter-authoring.md](adapter-authoring.md), [examples/adapter-integration-note.md](examples/adapter-integration-note.md), offline [`scripts/demo_adapter_path.sh`](../scripts/demo_adapter_path.sh) |
| Scientists / labs | [private-evaluation-pilot.md](private-evaluation-pilot.md), [examples/method-pilot-report.md](examples/method-pilot-report.md), [examples/studio-walkthrough.md](examples/studio-walkthrough.md) |
| Orientation | [START_HERE.md](../START_HERE.md), [outreach-one-pager.md](outreach-one-pager.md) |

## Explicit non-goals (this roadmap page)

- Unlocking §12 performance claims
- Fabricating issues #3 / #5 / #7 evidence
- Ranking AI reviewers
- Building hosted production ops (#18) as a community requirement

## Related

- [MILESTONES.md](MILESTONES.md) — authoritative status and §12 matrix
- [v0.9-beta-go-no-go.md](v0.9-beta-go-no-go.md)
- [ADOPTERS.md](../ADOPTERS.md)
- [examples/README.md](examples/README.md)
