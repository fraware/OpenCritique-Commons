# Signing-key governance and rotation

Issue #4 tracks the **production** ceremony. Development-channel keys are published
via `scripts/signing_ceremony_dev.py` (Wave 4.1). A valid signature establishes
**artifact integrity** relative to a trusted key. It does **not** establish
scientific correctness or authorize performance claims.

## Channels

| Channel | Trust-store contents | Verification policy |
|---|---|---|
| `development` | Offline root + online release public keys (committed) | `policy_mode=development` |
| `production` | Empty until separate production ceremony | `policy_mode=production` rejects development-only keys |

Development keys are unmistakably labeled (`ed25519:DEV-…`) and list `development`
in `channels` without `production`. Production verification fail-closes on them.

## Key roles

| Role | Purpose | Production signing |
|---|---|---|
| `offline_root` | Offline root of trust; publishes and revokes release keys | Rare / ceremony |
| `online_release` | Signs public scorecard envelopes for published releases | Yes (production channel only) |
| `test` | Ephemeral CI / developer keys; unmistakably marked | **Rejected** |

Separation of duties: root operators must not routinely hold online release private
keys on networked build hosts.

## Development ceremony

```bash
# Private keys go OUTSIDE the repo (temp dir by default).
python scripts/signing_ceremony_dev.py --private-dir /secure/offline/dev-keys
```

Only public keys and roles are written to `trust/scorecard-trust-store.json`.
Private keys must never be committed.

## Trust store

Machine-readable format: `TrustStore` (`opencritique_evaluation.trust`).

Published through at least two independent channels (documented in
`published_channels`), for example:

1. This repository path `trust/scorecard-trust-store.json` (public keys only)
2. Release attestation notes / signed Git tags referencing key fingerprints

Private keys **never** enter the repository, wheels, CI logs, test fixtures, or
release archives. Tests generate ephemeral keys in temporary directories, and the
development ceremony keeps private material under `--private-dir`.

## Validity, rotation, revocation

- Each trusted key has `not_before` / optional `not_after` and a `status`.
- Rotation records (`RotationStatement`) link retiring and successor keys while
  retaining historical verification (`policy_mode=historical`).
- Revocation records fail **current** development/production verification with an
  actionable reason (`revoked_key`).
- Unknown keys fail closed (`unknown_key`).
- Superseded keys verify only under `historical` policy so past scorecards remain
  attributable after rotation.
- Suspected private-key exposure: revoke immediately, rotate successor keys, publish
  revocation through both channels, and treat outstanding envelopes as untrusted
  under current policy (see `SECURITY.md`).

## CLI

```bash
opencritique evaluation keygen --private-key /secure/path/key.pem --public-key trust/keys/release.pem
opencritique evaluation sign-scorecard --scorecard scorecard.json --private-key /secure/path/key.pem
opencritique evaluation verify-scorecard \
  --envelope scorecard.signed.json \
  --trust-store trust/scorecard-trust-store.json \
  --policy-mode development
```

## Threat model coverage

- Substitution of scorecard payload
- Rollback / reuse of stale keys beyond validity
- Private-key compromise (see `SECURITY.md`)
- Unauthorized signing by untrusted, test, or development-only keys under production policy
- Stale-key acceptance after revocation or expiry

## Production ceremony checklist (issue #4)

Do **not** commit production private keys. Development-channel keys remain the
only in-repo trust material until this checklist completes outside the
repository.

| Step | Done when |
|---|---|
| Offline root generated on air-gapped or equivalent custody media | Root public fingerprint recorded |
| Online release key generated; root signs a rotation/issuance statement | Statement hash archived |
| Production public keys published on ≥2 independent channels | Channel URLs/ids listed in trust store `published_channels` |
| Custody, backup, dual-control, and incident response documented | Linked from SECURITY.md / ops runbook (not private key material) |
| Production trust store verified to reject unknown, revoked, test, and development-only keys | CI or witnessed ceremony transcript |
| Historical verification retained after first production rotation | `policy_mode=historical` proven against a retired key |
| Callers use `verify_envelope_detailed` with the production trust store | Boolean `verify_envelope` without trust material is not used in production |

Until issue #4 closes, release notes must state that only the **development**
signing channel is populated.
