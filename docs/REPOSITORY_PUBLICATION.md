# Repository publication integrity

OpenCritique Commons treats the public Git tree as part of the scientific
integrity boundary. A release is not considered published merely because a pull
request exists, a workflow reports success, or an archive was generated
elsewhere.

## Required public surface

The default branch must expose, at minimum:

- `src/opencritique_schema/models.py`
- `src/opencritique_registry/api.py`
- `src/opencritique_evaluation/engine.py`
- `src/opencritique_adapters/coarse.py`
- `src/opencritique_acquisition/models.py`

These paths are checked in the test suite.

## Prohibited publication residue

Temporary bootstrap directories, encoded transport fragments, private signing
material, and one-time repair workflows must not remain in the durable
repository tree. The test suite rejects known repair paths, including:

- `.bootstrap/`
- `.github/workflows/bootstrap-source.yml`
- `.github/workflows/publish-main.yml`
- `.github/workflows/publish-blobs.yml`
- `.github/workflows/repair-publish.yml`

Local inspection trees such as `_inspect_wheel/`, runtime smoke databases, and
scratch root notes (`issue*.md`) must remain untracked / gitignored.

## Validation rule

A source publication is accepted only when all of the following hold:

1. The required files exist in the Git tree.
2. A fresh clone can install the package with `pip install -e ".[dev]"`.
3. `bash scripts/check.sh` passes (compile, tests, import smoke).
4. Temporary publication machinery is absent.
5. Scientific-performance claims remain disabled until the natural-case and
   independent-adjudication gates are satisfied
   (`performance_claims_authorized=false`).

## Schema freeze vs engineering release

- Schema freeze identity: **`0.5.0a1`** (`SCHEMA_FREEZE_RELEASE`, golden hashes)
- Package / engineering release: **`0.6.0a0`**

Changing frozen schema bytes or canonicalization rules requires a major schema
bump and ADR — not merely a package version bump.

## Recovery record (`v0.5.0a1`)

Recovered package modules were republished from ZIP-carved source. Missing
evaluation orchestration and studio script modules were reimplemented against
recovered caller contracts. The historically advertised wheel SHA-256
`fdb22e42…` was **not** verified against a readable artifact during this
republication. See [ADR-0001](../governance/decisions/ADR-0001-source-recovery.md).

Cryptographic integrity of a distribution artifact would not establish
scientific correctness, benchmark completeness, or reviewer performance.
