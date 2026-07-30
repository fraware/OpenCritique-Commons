# Authoring a third adapter

Tutorial for adding a new upstream bridge into `opencritique_adapters`
**without** shipping a real third production upstream. Use this when you want
adapter **#3** (or later) as a sample-conformance path.

Copy the stubs under [`templates/adapter-skeleton/`](../templates/adapter-skeleton/)
and rename placeholders (`example` → your slug). Do **not** invent production
authenticity or set `performance_claims_authorized=true`.

## What an adapter does

An adapter turns **upstream-shaped review exports** into an
`EvaluationSubmission` that evaluation / scorecards understand. It is separate
from optional **live runners** (`opencritique_runners`), which invoke upstream
tools and write private exports under `runs/`.

| Layer | Package | Responsibility |
|---|---|---|
| Convert / map / loss | `opencritique_adapters` | Fixtures → submission; conversion-loss reporting |
| Live invoke (optional) | `opencritique_runners` | Manuscript → private export; see [runner-plugins.md](runner-plugins.md) |

Reference implementations: `coarse.py` / `coarse_loss.py` and
`openreviewer.py` / `openreviewer_loss.py`.

## Sample vs production rules

| Tree | Allowed claim |
|---|---|
| Maintainer-owned / synth fixtures under `fixtures/<slug>/` | Sample-adapter conformance only |
| `fixtures/<slug>/production/` | Rights-cleared authentic exports only — still **not** reviewer-quality claims |
| Private `runs/` from live runners | Operator-local evidence; never auto-promote |

Hard rules:

1. Pin a **sample** contract id (not a pretend Git SHA) for sample fixtures.
2. Keep `performance_claims_authorized=false` on contracts, maps, and reports.
3. Production `MANIFEST.json` stays fail-closed until real rights + volume land
   (see [adapter-authenticity.md](adapter-authenticity.md)). Do not fabricate
   `status=ready` or hashed production reviews.
4. Loss reports must separate sample results from a production section that can
   honestly say **NOT READY**.

## Skeleton checklist

1. **Contract** — `contract.py`: upstream contract version string, repository
   URL, sample adapter contract id, `PERFORMANCE_CLAIMS_AUTHORIZED = False`,
   optional field inventory for loss reports.
2. **Review models** — Pydantic models for the upstream export shape (extra
   fields allowed when upstream is loose; forbid inventing severity when the
   upstream does not provide it).
3. **Benchmark map** — JSON map linking `(case_id, case_version)` →
   `review_path`, plus optional abstain/failure entries. Mirror
   `fixtures/coarse/maps/synth-map.json` / OpenReviewer maps.
4. **`convert_*_benchmark`** — Load benchmark manifest + map; emit
   `EvaluationSubmission` with `SystemManifest` (`execution_mode="external"`,
   `code_commit` = sample contract id for sample fixtures).
5. **Loss profile** — Field-fate inventory (preserved / normalized / provisional /
   omitted) and aggregate stats; stamp claims locked.
6. **CLI** — Typer command under `opencritique adapters <slug>` (see
   `opencritique_adapters.cli`).
7. **Tests** — Fixture convert round-trip + claims-locked assertion. Skeleton
   ships a placeholder test you expand once fixtures exist.
8. **Fixtures layout** (when you add real samples):

   ```text
   fixtures/<slug>/
     UPSTREAM_CONTRACT.json
     maps/synth-map.json
     reviews/*.json
     production/          # blocked / empty until authentic exports
       MANIFEST.json
       MANIFEST.schema.json
       README.md
   ```

## Mapping concerns

Convert each upstream finding into `SubmittedConcern` with:

- Stable `local_id` (hash of case + upstream identity fields).
- Verbatim quote / anchor text when available; never silently invent geometry.
- Honest `evidence_summary` that conversion does **not** prove claim validity.
- Severity / confidence only when the upstream supplies them (or map through a
  documented enum, as Coarse does).

Abstain or fail cases explicitly in the map rather than dropping them.

## CLI smoke (sample path)

After wiring convert:

```bash
opencritique adapters <slug> \
  --manifest benchmarks/<bench>/manifest.json \
  --benchmark-root benchmarks/<bench> \
  --mapping fixtures/<slug>/maps/synth-map.json \
  --output <slug>-submission.json
```

Then evaluation / scorecard as in the README golden path. Scorecards must still
show **NOT AUTHORIZED** for scientific performance.

## Optional live runner

If the upstream can run locally or via BYOK, add a runner under
`opencritique_runners` that implements [`LiveRunnerPlugin`](runner-plugins.md)
and an optional `[live-<slug>]` extra in `pyproject.toml`. Live outputs stay
under `runs/`; refuse `fixtures/*/production/` writes.

## Out of scope for this tutorial

- Shipping a real third upstream with production MANIFESTs.
- Unlocking §12 performance claims.
- Hosted SaaS or expert scale (see deferred specs linked from
  [MILESTONES.md](MILESTONES.md)).
