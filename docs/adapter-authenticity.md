# Adapter authenticity playbook

Sample adapter fixtures exercise software conformance. They are **not** evidence
that Coarse or OpenReviewer reviews are scientifically reliable, and they do not
satisfy issues #3 or #5.

## Separation of concerns

| Tree | Purpose | Claim allowed |
|---|---|---|
| `fixtures/coarse/` (synth / sample) | Deterministic conversion + loss report | Sample-adapter conformance only |
| `fixtures/openreviewer/` (synth / sample) | Deterministic conversion + cross-adapter report | Sample-adapter conformance only |
| `fixtures/*/production/` | Rights-cleared authentic upstream exports (when available) | Production conversion fidelity only — still **not** reviewer-quality claims |
| `benchmarks/*-synth-v0.1/` | Synthetic matching demos | Descriptive only |

Upstream contract files (`fixtures/*/UPSTREAM_CONTRACT.json`) document the
**sample** adapter contract id. Production authenticity requires a distinct
fixture tree under `fixtures/*/production/` with `MANIFEST.json`
(`source=production`) and content hashes. Empty / `blocked` production trees
fail closed: CI asserts no fabricated review payloads and that `status=ready`
without ≥10 exports raises.

Loss and cross-adapter reports include an explicit `source=production` section
(see `ProductionSection` in `opencritique_adapters.production_fixtures`) separate
from sample results.

## How production exports enter the repo

1. Complete rights clearance per [rights-memorandum.md](rights-memorandum.md)
   (issue #7). Refuse uncleared manuscripts embedded in exports.
2. Obtain genuine Coarse exports (issue #3) or authentic OpenReviewer outputs
   (issue #5) with pinned upstream commit / release.
3. Place redistributable artifacts under:

   ```text
   fixtures/coarse/production/
   fixtures/openreviewer/production/
   ```

   Keep filenames and a `MANIFEST.json` that records upstream version, retrieval
   date, content hashes, and rights record ids.
4. Convert with the existing adapters **without** hand-editing JSON outputs.
5. Refresh conversion-loss / cross-adapter reports with an explicit
   `source=production` section separate from sample results.
6. Keep unresolved quotations unresolved; document ambiguous cases in the report.

## What must stay out

- Fabricated “natural” exports
- Confidential manuscript text without a written grant
- Marketing language that equates sample conformance with production validation
- Enabling `performance_claims_authorized`

## Exit for issues #3 / #5

Hard DoD lives on the GitHub issues. Closing either issue requires production
fixtures plus regenerated reports — not an update to sample contracts alone.
