# Signing-key governance and rotation

Issue #4 tracks the **production** ceremony. Development-channel keys are published
via `scripts/signing_ceremony_dev.py`. A valid signature establishes
**artifact integrity** relative to a trusted key. It does **not** establish
scientific correctness or authorize performance claims.

## Channels

| Channel | Trust-store contents | Verification policy |
|---|---|---|
| `development` | Offline root + online release public keys (committed) | `policy_mode=development` |
| `production` | Offline root + online release public keys (committed; private keys offline) | `policy_mode=production` rejects development-only keys |

Development keys are unmistakably labeled (`ed25519:DEV-…`) and list `development`
in `channels` without `production`. Production verification fail-closes on them.
Production keys are labeled (`ed25519:PROD-…`) and list `production` in `channels`.

**Current status:** production public keys (`PROD-ROOT` / `PROD-RELEASE`) are
published in `trust/scorecard-trust-store.json`. Private keys remain out of the
repository.

## Key roles

| Role | Purpose | Production signing |
|---|---|---|
| `offline_root` | Offline root of trust; publishes and revokes release keys; may also sign claim-authorization envelopes | Rare / ceremony |
| `online_release` | Signs public scorecard envelopes for published releases | Yes (production channel only) |
| `claim_authority` | Signs `SignedClaimAuthorizationEnvelope` decisions that unlock public claim scopes | Yes (claim envelopes only) |
| `evidence_authority` | Signs `SignedEvidenceEnvelope` scientific evidence attestations consumed by authenticity gates | Yes (evidence envelopes only) |
| `test` | Ephemeral CI / developer keys; unmistakably marked | **Rejected** |

Separation of duties: root operators must not routinely hold online release private
keys on networked build hosts. Scorecard integrity signatures (`online_release`) do
**not** authorize scientific performance claims. Public claim scopes require a
separately verified claim-authorization envelope signed by `claim_authority` or
`offline_root`. Scientific authenticity gates additionally require verified
evidence attestations signed by `evidence_authority` or `offline_root`.

## Claim-authorization envelopes

Public scientific scopes (`public_domain_bounded`, `public_comparative`) unlock only
after `verify_claim_authorization` succeeds against the production (or explicit
development/test) trust store:

1. Canonical decision bytes must match `payload_sha256`.
2. `key_id` must resolve in the trust store with an allowed role, active status,
   validity interval, and no revocation.
3. Ed25519 signature must verify.
4. Decision fields must bind to the live benchmark (`benchmark_id` / `version`,
   `case_set_hash`, recomputed manifest content hash, scoring-policy hash, matcher
   version/config hash, `domain_scope` / `use_scope`).
5. Wall-clock time must fall in `[issued_at, not_after]`.

A non-empty 64-hex `signed_authorization_manifest_digest` alone is **not**
authorization. `BenchmarkManifest.claim_authorization()`, `EvaluationResult`, and
`build_scorecard` fail closed without a verified envelope. Scorecard signing still
proves artifact integrity only; it does not bypass claim authorization.

## Scientific evidence attestations

Blocking scientific gates (`scripts/check_v09_scientific_gates.py`) verify
`SignedEvidenceEnvelope` artifacts under `governance/evidence/attestations/`:

| Kind | Gate subject examples |
|---|---|
| `natural_corpus` | Rights-cleared natural case IDs / ledger bindings |
| `reviewer_export_authenticity` | Production MANIFEST artifact content hashes |
| `expert_staffing` | Independent adjudicator IDs per domain |
| `matcher_audit_completion` | Completed dual-judgment audit sessions / judgment-set hash / count ≥100 |
| `holdout_custody` | Holdout freeze / custody binding (full model follow-on) |
| `independent_evaluation` | Expert-natural benchmark IDs with independent evaluation |

Verification (`verify_evidence_envelope`) mirrors claim-authorization checks and
emits a structured verification report (artifact path, content hash, signature
status, authority, bindings, failure reason, revocation status). Until real
envelopes exist, gates remain NO-GO with `missing_attestation` — not a false green
from Boolean JSON, roster status, or `sampled_count` alone.

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

## Production rotation drill checklist (no private keys)

Run this dry-run periodically **without** placing private keys in the repository,
CI logs, or chat. Private material stays on offline / HSM custody media only.

| Step | Operator action | Pass criterion |
|---|---|---|
| 1. Inventory | Confirm published `PROD-ROOT` / `PROD-RELEASE` fingerprints in `trust/scorecard-trust-store.json` match offline custody labels | Fingerprints match on ≥2 published channels |
| 2. Dual control | Two custodians present for any production rotation; neither alone holds both root and release private material | Dual-control log entry (ops, not in-repo) |
| 3. Successor issuance | Generate successor release key **offline**; root signs a `RotationStatement` | Statement hash archived outside repo |
| 4. Publish public only | Merge **public** successor key + rotation/revocation records into the trust store; never commit private PEMs | `git` diff shows public keys / statements only |
| 5. Fail-closed verify | Verify a known-good production envelope under `policy_mode=production`; confirm development-only and revoked keys fail | CI trust tests + witnessed verify transcript |
| 6. Historical retain | Verify a pre-rotation envelope under `policy_mode=historical` with the retired public key | Historical verify succeeds; current production rejects retired key |
| 7. Incident path | Walk the SECURITY.md compromise checklist verbally (revoke → rotate → republish) | Checklist signed off; no private key material recorded |

This drill does **not** authorize performance claims. It only proves signing
custody and rotation readiness for issue #4.

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

Do **not** commit production private keys. Run
`scripts/signing_ceremony_prod.py` with `--private-dir` **outside** the
repository. Development-channel keys remain development-only.

| Step | Done when | Status |
|---|---|---|
| Offline root generated on air-gapped or equivalent custody media | Root public fingerprint recorded | Met (public key published) |
| Online release key generated; root signs a rotation/issuance statement | Statement hash archived | Met (public key published) |
| Production public keys published on ≥2 independent channels | Channel URLs/ids listed in trust store `published_channels` | Met |
| Custody, backup, dual-control, and incident response documented | Linked from SECURITY.md / ops runbook (not private key material) | Met (see SECURITY.md) |
| Production trust store verified to reject unknown, revoked, test, and development-only keys | CI or witnessed ceremony transcript | Met (CI trust tests) |
| Historical verification retained after first production rotation | `policy_mode=historical` proven against a retired key | Pending first production rotation |
| Callers use `verify_envelope_detailed` with the production trust store | Boolean `verify_envelope` without trust material is not used in production | Met (CIR-04) |

## Boolean `verify_envelope` API

`verify_envelope` is a convenience boolean wrapper. It **requires** one of:

- `trusted_public_key_path` (PEM),
- `trust_store` / `trust_store_path`, or
- explicit `allow_untrusted_test=True` (ephemeral CI / unit tests only).

Calling it without trust material and without the opt-in flag raises `ValueError`
(fail closed). Production and development `verify_envelope_detailed` policies also
fail closed when no trust store or trusted PEM is supplied. Prefer
`verify_envelope_detailed` for all production verification paths.

## Production ceremony script

```bash
# Private keys go OUTSIDE the repo (temp dir by default).
python scripts/signing_ceremony_prod.py --private-dir /secure/offline/prod-keys
```

Only public keys and roles are merged into `trust/scorecard-trust-store.json`.
Private keys must never be committed. Development keys remain development-only.
