# Runner plugin contract

Formal interface for optional live upstream runners under
`opencritique_runners`. Sample **adapters** (convert/map/loss) are documented in
[adapter-authoring.md](adapter-authoring.md). This doc covers **runners**:
manuscript → private export under `runs/`.

## Protocol

Defined in `opencritique_runners.protocol`:

| Member | Role |
|---|---|
| `name` | Stable plugin id (`coarse`, `openreviewer`, …) |
| `live_extra` | `pyproject` optional-extra name, or `None` for import-only |
| `run(manuscript, **kwargs) -> RunnerRunResult` | `(review, provenance, markdown)` |
| `write_export(result, output, …) -> Path` | Serialize; refuse `fixtures/*/production/` |

`RunnerRunResult` normalizes the tuple the plan describes:
`review_model`, `provenance`, `markdown`.

## How shipped runners implement it

| Plugin | Module | `run` | `write_export` | Extra |
|---|---|---|---|---|
| Coarse | `coarse.CoarseRunnerPlugin` | wraps `run_coarse_review` | wraps `write_coarse_export` | `[live-coarse]` |
| OpenReviewer | `openreviewer.OpenReviewerRunnerPlugin` | wraps `run_openreviewer_review` / import | wraps `write_openreviewer_live_export` | `[live-openreviewer]` for HF local; import mode needs no extra |

Existing module-level functions remain the primary API. Plugin classes are thin
adapters for discovery / checklist conformance. CLI (`opencritique runners …`)
continues to call the functions directly.

## Checklist for a fourth runner

1. Add `run_*` + `write_*_export` in a new module under `opencritique_runners/`.
2. Call `assert_not_production_fixtures_path` on every write.
3. Stamp `evidence_class=private_live` and `performance_claims_authorized=false`.
4. Implement `LiveRunnerPlugin` (thin class wrapping those functions).
5. Optional: `[live-<slug>]` extra for heavy deps; keep default/`[dev]` free of
   paid-API or GPU deps.
6. Wire Typer commands; ASCII-safe banners only.
7. Mocked unit tests in default CI; never call paid APIs without secrets +
   explicit dispatch (see live-coarse smoke workflow).

## Claims boundary

Live runners deepen the **operator engineering** surface only. They do not:

- flip v0.9 authenticity gates;
- authorize §12 performance claims;
- auto-promote `runs/` into `fixtures/*/production/`.

See [adapter-authenticity.md](adapter-authenticity.md) and
[MILESTONES.md](MILESTONES.md).

For **sample** convert -> eval -> scorecard without paid APIs, use
[`scripts/demo_adapter_path.sh`](../scripts/demo_adapter_path.sh) /
[`.ps1`](../scripts/demo_adapter_path.ps1) (adapters path, not a live runner).
Document external adapters with
[examples/adapter-integration-note.md](examples/adapter-integration-note.md);
registry / checklist:
[community-adapters.md](community-adapters.md),
[compatibility-checklist.md](compatibility-checklist.md).
