# Security policy

## Reporting

Report suspected vulnerabilities or private-key exposure privately to the
repository maintainers via GitHub Security Advisories when available, or by
contacting the maintainer listed in `CITATION.cff`.

Do not open public issues that include private keys, credentials, or confidential
manuscript material.

## Scorecard signing compromise response

If an OpenCritique scorecard signing private key is suspected compromised:

1. **Contain** — stop using the key; remove it from online signing hosts.
2. **Revoke** — publish a `RevocationRecord` in the trust store through every
   declared publication channel; set key `status` to `revoked`.
3. **Rotate** — generate a successor key offline; publish a `RotationStatement`
   linking retiring and successor key ids; update `trust/scorecard-trust-store.json`.
4. **Preserve history** — historical scorecards signed before revocation remain
   verifiable under `policy_mode=historical` with the superseded/revoked context
   disclosed; do not silently rewrite past envelopes.
5. **Re-sign** — where policy requires, publish successor-signed envelopes that
   reference predecessor scorecard hashes; never mutate immutable scorecard ids.
6. **Disclose** — document the incident reference, time window, and affected
   artifacts without publishing private key material.

Test keys must be unmistakably marked and are rejected by production verification
policy. Development-channel keys are rejected under `policy_mode=production`.
A valid signature never authorizes scientific performance claims.

## Trust store today

`trust/scorecard-trust-store.json` publishes:

- Development-channel public keys (`ed25519:DEV-…`)
- Production-channel public keys (`ed25519:PROD-ROOT-…`, `ed25519:PROD-RELEASE-…`)

Private keys are never committed. Production private-key custody, backup,
dual-control, and incident response follow this document plus
[docs/signing-governance.md](docs/signing-governance.md). Ceremony private
material is generated only under an out-of-repo `--private-dir`
(`scripts/signing_ceremony_prod.py`).

## Repository invariants

- No production private keys in git, wheels, CI logs, or fixtures
- Secret scan runs in `scripts/check.sh` / CI
- Malicious document-graph fixtures are for security regression only
- `performance_claims_authorized` remains false until claim gates are met
