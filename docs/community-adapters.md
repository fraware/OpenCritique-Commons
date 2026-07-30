# Community adapters registry

Discovery surface for adapters that produce or consume OpenCritique Commons
interchange types. **Listing is not endorsement of reviewer quality.** Scientific
performance claims stay locked (`claims=false`) until §12 / v0.9 gates are met
with real evidence.

Schema freeze identity for interchange: `SCHEMA_FREEZE_RELEASE=0.5.0a1`
(package releases such as `0.6.0a0` may advance independently).

Machine-readable source of truth: [`community-adapters.json`](community-adapters.json)
validated by [`community-adapters.schema.json`](community-adapters.schema.json).

Related: [compatibility-checklist.md](compatibility-checklist.md),
[adapter-authoring.md](adapter-authoring.md),
[cross-adapter-conformance.md](cross-adapter-conformance.md),
[adapter-authenticity.md](adapter-authenticity.md).

## Registry

| slug | name | maintainer | status | evidence_class | claims | docs |
|---|---|---|---|---|---|---|
| `coarse` | Coarse | OpenCritique Commons (in-tree) | in-tree | sample | false | [adapter-authoring.md](adapter-authoring.md) |
| `openreviewer` | OpenReviewer | OpenCritique Commons (in-tree) | in-tree | sample | false | [adapter-authoring.md](adapter-authoring.md) |

Upstream repos: [Coarse](https://github.com/Davidvandijcke/coarse),
[OpenReviewer](https://github.com/maxidl/openreviewer).

## Field meanings

| Field | Meaning |
|---|---|
| `slug` | Stable lowercase id (`coarse`, `openreviewer`, …) |
| `name` | Human-readable adapter / upstream name |
| `maintainer` | Who owns the listing and docs |
| `repo_url` | Upstream or adapter repository URL |
| `status` | `in-tree` \| `external` \| `planned` |
| `evidence_class` | `sample` \| `private_live` \| `production` (honest) |
| `claims` | Always `false` until claim-authorization gates |
| `docs` | Link to authoring / integration notes |

`evidence_class=production` requires a rights-cleared
`fixtures/<slug>/production/MANIFEST.json` with `status=ready` and hashed
exports. Do not list production evidence without that tree. Private live runs
under `runs/` stay operator-local and never auto-promote.

## How to add or update an entry

1. Confirm the adapter meets [compatibility-checklist.md](compatibility-checklist.md)
   (interchange only; claims locked).
2. Open a PR that updates **both** `community-adapters.json` and the table above.
3. Keep `claims: false` and `performance_claims_authorized: false` on the
   registry root.
4. Run registry tests (see below) and optional
   `python scripts/check_adapter_compatibility.py` on your adapter path.
5. Maintainers review claim boundary + evidence_class honesty first.

## Validation

```bash
pytest -q tests/test_community_adapters_registry.py
python scripts/check_adapter_compatibility.py --registry docs/community-adapters.json
```

The compatibility helper is **not** part of default `scripts/check.sh`.
