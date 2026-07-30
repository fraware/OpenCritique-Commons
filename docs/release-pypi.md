# Publishing OpenCritique Commons to PyPI

Trusted Publisher (OIDC) release path for `opencritique-commons`. Until the
first successful publish, **install from git** remains the primary path.

Related workflow: [`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml).

## Release gates (required)

Every publish path (tag push or non-dry `workflow_dispatch`) must clear all of
the following before upload:

| Gate | How it is enforced |
|---|---|
| Successful **core CI** for the same commit | `verify-core-ci` waits for / asserts a successful `CI` workflow run on `github.sha`, including jobs `lint`, `test (3.12)`, `test (3.13)`, `packaging`, `secret-scan`, `publication-audit`, and `postgres` |
| `scripts/check.sh` | Re-run inside the `validate` job after `.[dev]` install |
| Clean wheel and sdist install | Fresh venvs install `dist/*.whl` and `dist/*.tar.gz`, then import the public packages |
| Provenance attestation | GitHub `actions/attest-build-provenance` on built distributions; PEP 740 attestations on upload via `pypa/gh-action-pypi-publish` (`attestations: true`) |
| Pinned third-party Action SHAs | All third-party `uses:` entries pin full commit SHAs (mutable tags such as `@v4` / `@release/v1` are not used) |
| Protected PyPI environment approval | `publish` job targets GitHub Environment `pypi` (or `testpypi`); production must require a reviewer before upload |

Dry-run (`workflow_dispatch` with `dry_run=true`) still runs the CI gate,
`check.sh`, clean installs, and GitHub provenance attestation; it skips the
`publish` job (no environment approval, no index upload).

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
   `testpypi`. **Required** production defaults for `pypi`:
   - Custom deployment branch / tag policy limited to tags matching `v*`
   - **Required reviewer** (manual approval before upload) — this is the
     protected-environment gate; without it, OIDC upload is not human-gated
   The `testpypi` environment should also require a reviewer unless rehearsals
   are deliberately unrestricted.

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

### Dry-run (validate only; no upload)

GitHub → Actions → **Publish to PyPI** → **Run workflow**:

- `dry_run`: `true` (default)
- `target`: `pypi` or `testpypi` (ignored when dry-run)

The job verifies core CI for the selected ref, runs `scripts/check.sh`, builds
sdist/wheel, proves clean installs, writes `RELEASE_MANIFEST.json` / checksums /
SBOM under `dist/`, attests provenance on GitHub, and skips
`pypa/gh-action-pypi-publish`.

### Real publish

1. Ensure Trusted Publisher is registered on PyPI (and the workflow is on the
   default branch).
2. Ensure the commit to release already has a green **CI** run (push to `main`
   or a PR) for that exact SHA — tag pushes do not themselves re-run `ci.yml`.
3. Ensure `pyproject.toml` version is correct and changelog notes are ready.
4. Tag and push (preferred; matches a tag-only `pypi` environment policy):

   ```bash
   git tag v0.6.0a0
   git push origin v0.6.0a0
   ```

5. Approve the pending `pypi` environment deployment (required reviewer).
6. `workflow_dispatch` with `dry_run=false` and `target=pypi` only works when
   the ref is allowed by the environment deployment policy (tag `v*` when
   tag-only). Prefer the tag push path for production.

First production publish may wait until credentials / publisher registration
exist; shipping the workflow and this doc is intentional so the path is ready.

## Post-publish checks

- Confirm the project page on PyPI shows the new version.
- Confirm PEP 740 attestations appear for the uploaded files (PyPI Integrity /
  attestation UI).
- Confirm GitHub artifact attestations exist for the workflow run.
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
| `verify-core-ci` fails: no successful CI run | Tagged / dispatched commit never had a green `CI` workflow; merge to `main` (or wait for PR CI) first |
| `verify-core-ci` fails: missing job | Core CI job names changed; update the required list in `publish-pypi.yml` |
| OIDC / Trusted Publisher failure | Workflow name, environment name, or repo owner mismatch on PyPI |
| Tag version assert fails | Tag not equal to `v` + `pyproject.toml` version |
| Environment waiting | GitHub Environment protection rules need approval (expected for `pypi`) |
| Upload 403 on TestPyPI | Separate Trusted Publisher must be registered on TestPyPI |
| Attestation / provenance step fails | Missing `id-token` / `attestations` permissions on the validate job |

## Non-goals

- Unlocking `performance_claims_authorized`
- Fabricating production MANIFESTs as part of a release
- Replacing git install documentation until the package is actually live
- Making the optional OpenReviewer CI job a publish blocker
