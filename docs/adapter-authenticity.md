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
without enough exports raises.

Loss and cross-adapter reports include an explicit `source=production` section
(see `ProductionSection` in `opencritique_adapters.production_fixtures`) separate
from sample results. When status is not `ready`, report markdown includes
**NOT READY** and refuses readiness language.

## External authenticity workstreams (A–F)

Engineering cannot substitute for these inputs. Process is ready; evidence is
not. **Hard rule: never fabricate exports, natural manuscripts, adjudicator IDs,
or natural decision counts.** Do not invent `MANIFEST` `ready` status or fake
natural denominators. Keep `performance_claims_authorized=false`.

```text
[A] Affirmative rights clearance (counsel/owners)
  ├─► [B] Coarse ≥10 production exports (#3)
  ├─► [C] OpenReviewer ≥5 authentic outputs (#5)
  └─► [F] Funded experts + ≥6 natural candidate cases (#14)
            └─► [D] ≥40 natural adjudicated cases + 2-domain staffing + holdout
                      └─► [E] ≥100 natural matcher-audit decisions (#6)
```

| ID | Workstream | External input | Definition of done | Engineering once inputs exist |
|---|---|---|---|---|
| **A** | Rights | Written grant for eval (+ redistribution if public) | Affirmative clearance recorded; negative finding alone does not unlock natural import | `opencritique-acquisition` import; case-level rights; ledger update |
| **B** | Coarse production (#3) | ≥10 genuine exports + pinned upstream | `fixtures/coarse/production/MANIFEST.json` `status=ready` with ≥10 hashed artifacts; ingest validate passes | Place under `reviews/`; refresh `docs/coarse-conversion-loss.*` |
| **C** | OpenReviewer production (#5) | ≥5 redistributable authentic outputs | Same for openreviewer (≥5); cross-adapter production section ready | Refresh `docs/cross-adapter-conformance.*` |
| **F** | Experts (#14) | Funding + recruited independent adjudicators | Compensation rates set; natural calibration slots cleared; staffing roster `ready` for ≥2 domains | Point calibration at natural cases; blinded primary/tie-break |
| **D** | Natural corpus | Rights-cleared natural cases | ≥40 natural adjudicated cases + holdout custody | Import, adjudicate, pilot scorecards with claims still locked |
| **E** | Matcher-audit (#6) | Natural match population + auditors | ≥100 natural audited decisions; `natural_dod_met` from session manifests | Stratified natural sessions under `corpus/matcher-audit/sessions/` |

Gate evaluator: `python scripts/check_v09_gates.py` (must exit **0** before
v0.9-beta GO). Evidence paths: [../governance/evidence/README.md](../governance/evidence/README.md).

Milestone tracking: [MILESTONES.md](MILESTONES.md) / [v0.9-beta-go-no-go.md](v0.9-beta-go-no-go.md).
§12 scientific performance claims stay locked until the claim-authorization matrix
is met — even after gates exit 0.

## How production exports enter the repo

1. Complete rights clearance per [rights-memorandum.md](rights-memorandum.md)
   (issue #7). Refuse uncleared manuscripts embedded in exports.
2. Obtain genuine Coarse exports (issue #3) or authentic OpenReviewer outputs
   (issue #5) with pinned upstream commit / release.
3. Place redistributable artifacts under:

   ```text
   fixtures/coarse/production/
     MANIFEST.json
     MANIFEST.schema.json
     reviews/<export-id>.json
   fixtures/openreviewer/production/
     MANIFEST.json
     MANIFEST.schema.json
     reviews/<export-id>.json
   ```

   Each `MANIFEST.json` artifact entry must include:

   | Field | Requirement |
   |---|---|
   | `relative_path` | Path under the production root (e.g. `reviews/export-01.json`) |
   | `content_sha256` | Lowercase hex SHA-256 of file bytes |
   | `byte_size` | Exact on-disk size |
   | `rights_record_id` | Must appear in top-level `rights_record_ids` |

   Top-level ready fields: `upstream_repository`, `upstream_commit_or_config`
   (not a sample contract id), `retrieval_date`, `rights_record_ids`,
   `artifacts` (≥10 Coarse / ≥5 OpenReviewer), `status=ready`,
   `performance_claims_authorized=false`.
4. Convert with the existing adapters **without** hand-editing JSON outputs.
5. Refresh conversion-loss / cross-adapter reports with an explicit
   `source=production` section separate from sample results.
6. Keep unresolved quotations unresolved; document ambiguous cases in the report.

Validate intake with:

```bash
python scripts/ingest_production_adapter_exports.py validate-tree --adapter coarse
python scripts/ingest_production_adapter_exports.py validate-tree --adapter openreviewer
```

## What must stay out

- Fabricated “natural” exports
- Confidential manuscript text without a written grant
- Marketing language that equates sample conformance with production validation
- Enabling `performance_claims_authorized`
- Inventing `MANIFEST` ready status or fake natural counts to satisfy gates

## Exit for issues #3 / #5

Hard DoD lives on the GitHub issues. Closing either issue requires production
fixtures plus regenerated reports — not an update to sample contracts alone.

## Private live run vs production promotion

Private live runner outputs under `runs/` (Coarse BYOK or OpenReviewer
import/HF-local) are **operator-local evidence**. They do not satisfy issues
#3 / #5 and must not flip `fixtures/*/production/MANIFEST.json` to `ready`.

```text
                    ┌─────────────────────────────┐
                    │ Live review under runs/     │
                    │ evidence_class=private_live │
                    │ claims authorized = false   │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              ▼                                       ▼
   Use privately (convert /                 Want redistributable
   eval / Studio / operator                 production authenticity?
   notes). Stay under runs/.                         │
                                                     ▼
                                    Rights clearance recorded? (A)
                                    (≥10 Coarse / ≥5 OpenReviewer)
                                                     │
                              no ──► keep private; gates stay NO-GO
                                                     │ yes
                                                     ▼
                                    Build package **outside** runs/
                                    with MANIFEST + hashed reviews +
                                    rights_record_ids + upstream pin
                                                     │
                                                     ▼
                                    ingest_production_adapter_exports.py
                                      validate → stage (--no-dry-run)
                                    (staging from runs/ is refused)
                                                     │
                                                     ▼
                                    check_v09_gates.py still fail-closed
                                    until all A–F evidence lands
```

### Executable playbook (operator checklist)

| Step | Workstream | Command / artifact | Fail-closed rule |
|---|---|---|---|
| 1 | **A Rights** | Operator writes grant text; dry-run `opencritique acquisition import-approved-profile <profile.json>` (default `--dry-run`) for a **user-owned** manuscript | Refuse uncleared manuscripts; claims stay false |
| 2 | Live export | Coarse: `pip install -e ".[live-coarse]"` then `opencritique runners coarse` / `pipeline coarse` → `runs/coarse/…`; OpenReviewer: `opencritique runners openreviewer --from-export …` → `runs/openreviewer/…` (or `.[live-openreviewer]` + GPU) | Refuse writing under `fixtures/*/production/`; BYOK key does not run OpenReviewer |
| 3 | Private use | Convert / evaluate / Studio against private paths | Do not treat metrics as scientific claims |
| 4 | **B/C Production** | After ≥10 / ≥5 **redistributable** exports + rights: assemble package **outside** `runs/`; `python scripts/ingest_production_adapter_exports.py validate --adapter … --package …` then `stage` | **Refuse auto-promote from `runs/`**; never invent `ready` |
| 5 | **F Experts** | Rates + staffing evidence under `governance/evidence/` | Roster stays blocked until filled |
| 6 | **D/E Corpus + matcher-audit** | Natural sessions under `corpus/matcher-audit/sessions/` | Gates read evidence; no fabricated counts |
| 7 | Gate check | `python scripts/check_v09_gates.py` | Must exit **non-zero** (NO-GO) until real evidence lands; never sets `performance_claims_authorized=true` |

Hard engineering guards:

- `opencritique_runners.paths.assert_not_production_fixtures_path` — live CLI will not write into production fixture trees.
- `opencritique_runners.paths.assert_package_not_private_runs` — `stage_validated_package` refuses packages under `runs/` / `.runtime-live/` / `.demo-e2e/`.
- Production MANIFEST validators reject `performance_claims_authorized=true` and sample contract ids as upstream pins.

## Evidence promotion checklist

Promote **only** after rights + volume. Never copy or symlink `runs/` into
`fixtures/*/production/`. Staging from private live trees is refused.

| Gate | Ready when | Still fail-closed if |
|---|---|---|
| **A Rights** | Written grant / ledger entry for eval (+ redistribution if public) | Uncleared manuscript text in exports |
| **Volume** | ≥10 Coarse **or** ≥5 OpenReviewer redistributable hashed artifacts | Private `runs/` count alone (wrong evidence class) |
| **Package** | Directory **outside** `runs/` / `.runtime-live/` / `.demo-e2e/` with `MANIFEST.json` (`source=production`, hashes, `rights_record_ids`, upstream pin) | Package rooted under private live paths |
| **Ingest** | `validate` then `stage` via `scripts/ingest_production_adapter_exports.py` | Skipping validate; hand-editing review JSON; inventing `status=ready` |
| **Claims flag** | `performance_claims_authorized=false` on every production MANIFEST | Any attempt to set the flag `true` |
| **F Staffing** | Real adjudicator IDs in `governance/evidence/natural-adjudication-staffing.json` for ≥2 domains | Empty / blocked roster |
| **F Calibration** | Natural calibration seed slots cleared with real case/task IDs | `status=blocked` / empty `tasks` in calibration policy |
| **D/E Natural** | ≥40 natural adjudicated cases + holdout; ≥100 natural matcher-audit decisions in session manifests | Fabricated denominators or sample-only sessions |

Promotion commands (after the package exists **outside** `runs/`):

```bash
python scripts/ingest_production_adapter_exports.py validate \
  --adapter coarse \
  --package path/to/rights-cleared-package

python scripts/ingest_production_adapter_exports.py stage \
  --adapter coarse \
  --package path/to/rights-cleared-package \
  --no-dry-run
```

Same pattern for `--adapter openreviewer` (minimum ≥5 artifacts).

Staffing and natural calibration remain **fail-closed** until filled with real
IDs — see [expert-program-ops.md](expert-program-ops.md) and
[../governance/evidence/README.md](../governance/evidence/README.md). Private lab
pilots: [private-evaluation-pilot.md](private-evaluation-pilot.md).

Confirm gates still NO-GO without evidence:

```bash
python scripts/check_v09_gates.py
# expected: non-zero exit; performance_claims_authorized=false (enforced)
```
