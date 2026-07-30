# Publishing OpenCritique Commons to PyPI

Trusted Publisher (OIDC) release path for `opencritique-commons`. Until the
first successful publish, **install from git** remains the primary path.

Related workflow: [`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml).

## Prerequisites (one-time on PyPI)

1. Create or claim the project `opencritique-commons` on
   [PyPI](https://pypi.org/) (and optionally [TestPyPI](https://test.pypi.org/)).
2. Under **Publishing** → **Trusted publishers**, add a GitHub publisher:
   - Owner: `fraware`
   - Repository: `OpenCritique-Commons`
   - Workflow: `publish-pypi.yml`
   - Environment name: `pypi` (must match the workflow `environment:`)
3. Optional TestPyPI publisher with environment name `testpypi` for dry
   rehearsals against TestPyPI.
4. In the GitHub repo, create Environments named `pypi` and (optional)
   `testpypi`. Recommended production defaults for `pypi`:
   - Custom deployment branch policy limited to tags matching `v*`
   - Required reviewer (manual approval before upload)
   The `testpypi` environment can stay unrestricted for rehearsals.

No long-lived PyPI API tokens are required when Trusted Publishing is configured.

The workflow file must exist on the default branch before Actions can list or
dispatch **Publish to PyPI**. Until then, only local builds / future merges
apply.

## Version and tag alignment

| Surface | Rule |
|---|---|
| `pyproject.toml` `[project].version` | Source of truth for the built distribution |
| Git tag | Must be `v` + that version (example: version `0.6.0a0` → tag `v0.6.0a0`) |
| Schema freeze | Unrelated to package version; interchange remains `SCHEMA_FREEZE_RELEASE=0.5.0a1` |

Mismatch between tag and `pyproject.toml` version fails the workflow before
upload.

## How to run

### Dry-run (build only; no upload)

GitHub → Actions → **Publish to PyPI** → **Run workflow**:

- `dry_run`: `true` (default)
- `target`: `pypi` or `testpypi` (ignored when dry-run)

The job builds sdist/wheel, writes `RELEASE_MANIFEST.json` / checksums / SBOM
under `dist/`, and skips `pypa/gh-action-pypi-publish`.

### Real publish

1. Ensure Trusted Publisher is registered on PyPI (and the workflow is on the
   default branch).
2. Ensure `pyproject.toml` version is correct and changelog notes are ready.
3. Tag and push (preferred; matches a tag-only `pypi` environment policy):

   ```bash
   git tag v0.6.0a0
   git push origin v0.6.0a0
   ```

4. Approve the pending `pypi` environment deployment if a required reviewer is
   configured.
5. `workflow_dispatch` with `dry_run=false` and `target=pypi` only works when
   the ref is allowed by the environment deployment policy (tag `v*` when
   tag-only). Prefer the tag push path for production.

First production publish may wait until credentials / publisher registration
exist; shipping the workflow and this doc is intentional so the path is ready.

## Post-publish checks

- Confirm the project page on PyPI shows the new version.
- Smoke-install in a clean venv:

  ```bash
  python -m pip install opencritique-commons==<version>
  python -c "from opencritique_schema.registry import SCHEMA_FREEZE_RELEASE; assert SCHEMA_FREEZE_RELEASE == '0.5.0a1'"
  ```

- Claims remain unauthorized; do not frame the release as a scientific
  performance unlock.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| OIDC / Trusted Publisher failure | Workflow name, environment name, or repo owner mismatch on PyPI |
| Tag version assert fails | Tag not equal to `v` + `pyproject.toml` version |
| Environment waiting | GitHub Environment protection rules need approval |
| Upload 403 on TestPyPI | Separate Trusted Publisher must be registered on TestPyPI |

## Non-goals

- Unlocking `performance_claims_authorized`
- Fabricating production MANIFESTs as part of a release
- Replacing git install documentation until the package is actually live
