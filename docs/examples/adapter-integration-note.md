# Adapter integration note (template)

Use this when documenting an **external** or community adapter that
interoperates with OpenCritique Commons schemas. Compatibility means
**interchange** — not endorsement of reviewer quality.

**Non-claims:** `performance_claims_authorized=false`. Do not equate sample
fixtures or private live exports with production authenticity. Do not claim
precision/recall or comparative rankings as authorized scientific results.

Copy this file into a PR description, adapter repo `README`, or a note linked
from [community-adapters.md](../community-adapters.md).

---

## Identity

| Field | Value |
|---|---|
| Adapter slug | |
| Display name | |
| Maintainer / contact | |
| Source repo URL | |
| Status | `in-tree` / `external` / `planned` |
| Evidence class | `sample` / `private_live` / `production` (honest) |
| Claims authorized | **false** (required until §12 / v0.9 gates) |

## What this adapter does

One short paragraph: upstream export shape -> OpenCritique
`EvaluationSubmission` (convert / map / loss). Separate optional live runner
behavior if any.

## Interchange checklist (software)

Confirm before claiming "OpenCritique-compatible" for interchange only:

- [ ] Produces or consumes frozen schema types (cite `SCHEMA_FREEZE_RELEASE`)
- [ ] Documented convert path or export mapping
- [ ] Sample contract id pinned for sample fixtures (not a pretend production SHA)
- [ ] Claims locked on contracts, maps, reports, scorecards
- [ ] Rights posture stated for any redistributed fixtures
- [ ] Followed [compatibility-checklist.md](../compatibility-checklist.md)

## How to run (sample / offline)

```bash
# Replace placeholders with your paths
opencritique adapters <slug> \
  --manifest benchmarks/<bench>/manifest.json \
  --benchmark-root benchmarks/<bench> \
  --mapping fixtures/<slug>/maps/synth-map.json \
  --output <slug>-submission.json
```

Then evaluation / scorecard as in the README golden path. Expect
`NOT AUTHORIZED`. Offline demo mirror:
[`scripts/demo_adapter_path.sh`](../../scripts/demo_adapter_path.sh) /
[`.ps1`](../../scripts/demo_adapter_path.ps1).

## Conversion loss and limitations

- Field fate (preserved / normalized / provisional / omitted):
-
- Known upstream gaps:
-
- Production section status (honest **NOT READY** until authentic exports):

## What this note does **not** claim

- Reviewer quality, accuracy, or "beats system X"
- Production MANIFEST readiness without rights + volume evidence
- Unlock of `performance_claims_authorized`

## Registry listing

To appear in the community registry, open a PR updating
`docs/community-adapters.json` and `docs/community-adapters.md` after the
compatibility checklist. See [community-adapters.md](../community-adapters.md).

## Related

- [adapter-authoring.md](../adapter-authoring.md)
- [runner-plugins.md](../runner-plugins.md) (optional live path)
- [adapter-authenticity.md](../adapter-authenticity.md)
- [examples README](README.md)
