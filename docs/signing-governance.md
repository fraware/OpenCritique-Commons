# Signing-key governance and rotation

Issue #4 / PR6. A valid signature establishes **artifact integrity** relative to a
trusted key. It does **not** establish scientific correctness or authorize
performance claims.

## Key roles

| Role | Purpose | Production signing |
|---|---|---|
| `offline_root` | Offline root of trust; publishes and revokes release keys | Rare / ceremony |
| `online_release` | Signs public scorecard envelopes for published releases | Yes |
| `test` | Ephemeral CI / developer keys; unmistakably marked | **Rejected** |

Separation of duties: root operators must not routinely hold online release private
keys on networked build hosts.

## Trust store

Machine-readable format: `TrustStore` (`opencritique_evaluation.trust`).

Published through at least two independent channels (documented in
`published_channels`), for example:

1. This repository path `trust/scorecard-trust-store.json` (public keys only)
2. Release attestation notes / signed Git tags referencing key fingerprints

Private keys **never** enter the repository, wheels, CI logs, test fixtures, or
release archives. Tests generate ephemeral keys in temporary directories.

## Validity, rotation, revocation

- Each trusted key has `not_before` / optional `not_after` and a `status`.
- Rotation records (`RotationStatement`) link retiring and successor keys while
  retaining historical verification (`policy_mode=historical`).
- Revocation records fail **current** production verification with an actionable
  reason (`revoked_key`).
- Unknown keys fail closed (`unknown_key`).
- Superseded keys verify only under `historical` policy so past scorecards remain
  attributable after rotation.

## CLI

```bash
opencritique evaluation keygen --private-key /secure/path/key.pem --public-key trust/keys/release.pem
opencritique evaluation sign-scorecard --scorecard scorecard.json --private-key /secure/path/key.pem
opencritique evaluation verify-scorecard \
  --envelope scorecard.signed.json \
  --trust-store trust/scorecard-trust-store.json \
  --policy-mode production
```

## Threat model coverage

- Substitution of scorecard payload
- Rollback / reuse of stale keys beyond validity
- Private-key compromise (see `SECURITY.md`)
- Unauthorized signing by untrusted or test keys
- Stale-key acceptance after revocation or expiry
