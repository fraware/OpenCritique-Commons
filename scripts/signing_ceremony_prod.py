"""Offline production-channel Ed25519 signing ceremony (issue #4).

Generates production root and release keypairs outside the repository, then
merges **public keys only** into ``trust/scorecard-trust-store.json``.

Private keys are written only under ``--private-dir`` (default: a temporary
directory outside the repo). Never commit private material.

Development-channel keys already in the store are preserved and remain
development-only (rejected under ``policy_mode=production``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from opencritique_evaluation.signing import generate_keypair
from opencritique_evaluation.trust import (
    KeyRole,
    KeyStatus,
    TrustPolicyMode,
    TrustStore,
    build_trusted_key_record,
    load_trust_store,
    write_trust_store,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / "trust" / "scorecard-trust-store.json"
PROD_CHANNELS = [
    "production",
    "https://github.com/fraware/OpenCritique-Commons/blob/main/trust/scorecard-trust-store.json",
    "https://github.com/fraware/OpenCritique-Commons/releases",
]


def _issuance_statement(
    *,
    root_key_id: str,
    release_key_id: str,
    issued_at: datetime,
) -> dict[str, str]:
    body = {
        "statement_type": "production_key_issuance",
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "offline_root_key_id": root_key_id,
        "online_release_key_id": release_key_id,
        "channels": list(PROD_CHANNELS),
        "claim_boundary": (
            "A valid signature establishes artifact integrity only; "
            "it does not authorize scientific performance claims."
        ),
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body["statement_sha256"] = hashlib.sha256(canonical).hexdigest()
    return body


def run_ceremony(
    *,
    store_path: Path,
    private_dir: Path,
    not_before: datetime | None = None,
    dry_run: bool = False,
) -> TrustStore:
    private_dir.mkdir(parents=True, exist_ok=True)
    now = not_before or datetime.now(UTC)
    root_priv = private_dir / "prod-offline-root.pem"
    root_pub = private_dir / "prod-offline-root.pub.pem"
    release_priv = private_dir / "prod-online-release.pem"
    release_pub = private_dir / "prod-online-release.pub.pem"

    generate_keypair(root_priv, root_pub)
    generate_keypair(release_priv, release_pub)

    root = build_trusted_key_record(
        public_key_path=root_pub,
        role=KeyRole.OFFLINE_ROOT,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(minutes=1),
        not_after=now + timedelta(days=365 * 5),
        channels=list(PROD_CHANNELS),
        notes=(
            "Production-channel offline root. Custody outside the repository. "
            "Private key must never be committed."
        ),
    )
    root = root.model_copy(
        update={"key_id": f"ed25519:PROD-ROOT-{root.key_id.removeprefix('ed25519:')}"}
    )
    release = build_trusted_key_record(
        public_key_path=release_pub,
        role=KeyRole.ONLINE_RELEASE,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(minutes=1),
        not_after=now + timedelta(days=365),
        channels=list(PROD_CHANNELS),
        notes=(
            "Production-channel online release key. Authorized for production "
            "scorecard publication under policy_mode=production."
        ),
    )
    release = release.model_copy(
        update={
            "key_id": f"ed25519:PROD-RELEASE-{release.key_id.removeprefix('ed25519:')}"
        }
    )
    statement = _issuance_statement(
        root_key_id=root.key_id,
        release_key_id=release.key_id,
        issued_at=now,
    )
    (private_dir / "issuance-statement.json").write_text(
        json.dumps(statement, indent=2) + "\n",
        encoding="utf-8",
    )

    existing = (
        load_trust_store(store_path)
        if store_path.is_file()
        else TrustStore(
            store_id="opencritique-commons-scorecard-trust",
            policy_mode_default=TrustPolicyMode.PRODUCTION,
            keys=[],
            published_channels=[],
        )
    )
    # Drop any prior production-channel keys so re-runs replace cleanly.
    retained = [
        key
        for key in existing.keys
        if "production" not in {c.lower() for c in key.channels}
    ]
    channels = list(
        dict.fromkeys([*existing.published_channels, *PROD_CHANNELS[1:]])
    )
    store = TrustStore(
        store_id=existing.store_id,
        policy_mode_default=TrustPolicyMode.PRODUCTION,
        keys=[*retained, root, release],
        revocations=list(existing.revocations),
        rotations=list(existing.rotations),
        published_channels=channels,
        updated_at=now,
        notes=(
            "Public keys only. Development-channel keys are development-only; "
            "production-channel keys are present after the production ceremony "
            "(issue #4). Private keys are never stored in this repository. "
            f"Issuance statement SHA-256: {statement['statement_sha256']}."
        ),
    )
    if dry_run:
        (private_dir / "ceremony-manifest-dry-run.json").write_text(
            json.dumps(
                {
                    "dry_run": True,
                    "would_write_store": str(store_path),
                    "production_key_ids": [root.key_id, release.key_id],
                    "issuance_sha256": statement["statement_sha256"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return store

    write_trust_store(store, store_path)
    manifest = {
        "store_path": str(store_path),
        "private_dir": str(private_dir),
        "issuance_sha256": statement["statement_sha256"],
        "keys": [
            {"role": root.role.value, "key_id": root.key_id, "public": str(root_pub)},
            {
                "role": release.role.value,
                "key_id": release.key_id,
                "public": str(release_pub),
            },
        ],
        "warning": "Keep private_dir offline; do not commit *.pem private keys.",
        "published_channels": channels,
    }
    (private_dir / "ceremony-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE,
        help="Trust store JSON path (public keys only)",
    )
    parser.add_argument(
        "--private-dir",
        type=Path,
        default=None,
        help="Directory for private keys (outside the repo). Defaults to a temp dir.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate keys and statement without writing the trust store",
    )
    args = parser.parse_args()
    private_dir = args.private_dir
    if private_dir is None:
        private_dir = Path(tempfile.mkdtemp(prefix="opencritique-prod-signing-"))
    # Refuse to write private keys into the repository tree.
    try:
        private_dir.resolve().relative_to(ROOT.resolve())
        raise SystemExit(
            f"refusing to place production private keys under the repo: {private_dir}"
        )
    except ValueError:
        pass
    store = run_ceremony(
        store_path=args.store,
        private_dir=private_dir,
        dry_run=args.dry_run,
    )
    prod_keys = [
        key for key in store.keys if "production" in {c.lower() for c in key.channels}
    ]
    action = "dry-run prepared" if args.dry_run else "wrote"
    print(
        f"{action} trust store {args.store} with {len(prod_keys)} production public keys "
        f"(total keys={len(store.keys)})"
    )
    print(f"private keys (KEEP OFFLINE): {private_dir}")
    for key in prod_keys:
        print(f"  {key.role.value}: {key.key_id}")


if __name__ == "__main__":
    main()
