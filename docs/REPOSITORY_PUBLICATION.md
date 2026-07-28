# Repository publication integrity

OpenCritique Commons treats the public Git tree as part of the scientific integrity boundary. A release is not considered published merely because a pull request exists, a workflow reports success, or an archive was generated elsewhere.

## Required public surface

The default branch must expose, at minimum:

- `src/opencritique_schema/models.py`;
- `src/opencritique_registry/api.py`;
- `src/opencritique_evaluation/engine.py`;
- `src/opencritique_adapters/coarse.py`;
- `src/opencritique_acquisition/models.py`.

These paths are checked in the test suite.

## Prohibited publication residue

Temporary bootstrap directories, encoded transport fragments, private signing material, and one-time repair workflows must not remain in the durable repository tree. The test suite rejects known repair paths.

## Validation rule

A source publication is accepted only when all of the following hold:

1. GitHub exposes the required files from the default branch through its contents API.
2. A fresh public clone contains the same files.
3. The package installs from that clone.
4. Python compilation and the automated test suite pass.
5. Temporary publication machinery is absent.
6. Scientific-performance claims remain disabled until the natural-case and independent-adjudication gates are satisfied.

## v0.5-alpha recovery record

The source used for the repair was reconstructed from the validated wheel with SHA-256:

```text
fdb22e4266b973f277b06b950040ffbffb121913b2b1d127f1aec9440d9dbf83
```

GitHub verified the checksum before extraction, installed the extracted packages, and ran the repository tests before committing the source. The transport and one-time publisher were then removed.

Cryptographic integrity of the distribution artifact does not establish scientific correctness, benchmark completeness, or reviewer performance.
