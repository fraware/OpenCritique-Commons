"""Offline development-channel Ed25519 signing ceremony.

Generates development root and release keypairs outside the repository, then
writes **public keys only** into ``trust/scorecard-trust-store.json``.

Private keys are written only under ``--private-dir`` (default: a temporary
directory outside the repo). Never commit private material.
"""

from __future__ import annotations

import argparse
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
    write_trust_store,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / "trust" / "scorecard-trust-store.json"
DEV_CHANNELS = [
    "development",
    "https://github.com/fraware/OpenCritique-Commons/blob/main/trust/scorecard-trust-store.json",
    "https://github.com/fraware/OpenCritique-Commons/releases",
]


def run_ceremony(
    *,
    store_path: Path,
    private_dir: Path,
    not_before: datetime | None = None,
) -> TrustStore:
    private_dir.mkdir(parents=True, exist_ok=True)
    now = not_before or datetime.now(UTC)
    root_priv = private_dir / "dev-offline-root.pem"
    root_pub = private_dir / "dev-offline-root.pub.pem"
    release_priv = private_dir / "dev-online-release.pem"
    release_pub = private_dir / "dev-online-release.pub.pem"

    generate_keypair(root_priv, root_pub)
    generate_keypair(release_priv, release_pub)

    root = build_trusted_key_record(
        public_key_path=root_pub,
        role=KeyRole.OFFLINE_ROOT,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(minutes=1),
        not_after=now + timedelta(days=365 * 5),
        channels=list(DEV_CHANNELS),
        notes=(
            "Development-channel offline root. Not authorized for production "
            "scorecard publication. Production keys require a separate ceremony."
        ),
        key_id_override=None,
    )
    # Mark development channel unambiguously in key_id prefix for operators.
    root = root.model_copy(
        update={"key_id": f"ed25519:DEV-ROOT-{root.key_id.removeprefix('ed25519:')}"}
    )
    release = build_trusted_key_record(
        public_key_path=release_pub,
        role=KeyRole.ONLINE_RELEASE,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(minutes=1),
        not_after=now + timedelta(days=365),
        channels=list(DEV_CHANNELS),
        notes=(
            "Development-channel online release key. Reject under production "
            "policy unless channels include 'production'."
        ),
    )
    release = release.model_copy(
        update={
            "key_id": f"ed25519:DEV-RELEASE-{release.key_id.removeprefix('ed25519:')}"
        }
    )

    store = TrustStore(
        store_id="opencritique-commons-scorecard-trust",
        policy_mode_default=TrustPolicyMode.PRODUCTION,
        keys=[root, release],
        revocations=[],
        rotations=[],
        published_channels=list(DEV_CHANNELS[1:]),
        updated_at=now,
        notes=(
            "Development-channel public keys only. Production-channel keys are "
            "absent until a separate production ceremony (issue #4). Private keys "
            "are never stored in this repository."
        ),
    )
    write_trust_store(store, store_path)
    manifest = {
        "store_path": str(store_path),
        "private_dir": str(private_dir),
        "keys": [
            {"role": root.role.value, "key_id": root.key_id, "public": str(root_pub)},
            {
                "role": release.role.value,
                "key_id": release.key_id,
                "public": str(release_pub),
            },
        ],
        "warning": "Keep private_dir offline; do not commit *.pem private keys.",
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
    args = parser.parse_args()
    private_dir = args.private_dir
    if private_dir is None:
        private_dir = Path(tempfile.mkdtemp(prefix="opencritique-dev-signing-"))
    store = run_ceremony(store_path=args.store, private_dir=private_dir)
    print(f"wrote trust store {args.store} with {len(store.keys)} development public keys")
    print(f"private keys (KEEP OFFLINE): {private_dir}")
    for key in store.keys:
        print(f"  {key.role.value}: {key.key_id}")


if __name__ == "__main__":
    main()
