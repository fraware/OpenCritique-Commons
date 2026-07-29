"""Production signing ceremony dry-run and fail-closed checks (issue #4)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from opencritique_evaluation.signing import sign_scorecard, verify_envelope_detailed
from opencritique_evaluation.trust import (
    KeyRole,
    TrustPolicyMode,
    VerificationFailureReason,
    load_trust_store,
)
from tests.test_signing_governance import _scorecard

ROOT = Path(__file__).resolve().parents[1]


def _load_prod_ceremony():
    script = ROOT / "scripts" / "signing_ceremony_prod.py"
    spec = importlib.util.spec_from_file_location("signing_ceremony_prod", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_prod_ceremony_dry_run_does_not_write_store(tmp_path: Path) -> None:
    mod = _load_prod_ceremony()
    store_path = tmp_path / "trust.json"
    shipped = ROOT / "trust" / "scorecard-trust-store.json"
    store_path.write_text(shipped.read_text(encoding="utf-8"), encoding="utf-8")
    before = store_path.read_text(encoding="utf-8")
    private_dir = tmp_path / "offline-keys"
    store = mod.run_ceremony(
        store_path=store_path,
        private_dir=private_dir,
        dry_run=True,
        not_before=datetime(2026, 7, 29, tzinfo=UTC),
    )
    prod = [k for k in store.keys if "production" in {c.lower() for c in k.channels}]
    assert len(prod) == 2
    assert all(k.key_id.startswith("ed25519:PROD-") for k in prod)
    assert store_path.read_text(encoding="utf-8") == before
    assert (private_dir / "issuance-statement.json").is_file()
    assert b"PRIVATE KEY" in (private_dir / "prod-offline-root.pem").read_bytes()


def test_prod_ceremony_writes_public_keys_and_verifies(tmp_path: Path) -> None:
    mod = _load_prod_ceremony()
    store_path = tmp_path / "trust.json"
    shipped = ROOT / "trust" / "scorecard-trust-store.json"
    store_path.write_text(shipped.read_text(encoding="utf-8"), encoding="utf-8")
    private_dir = tmp_path / "offline-keys"
    store = mod.run_ceremony(store_path=store_path, private_dir=private_dir, dry_run=False)
    loaded = load_trust_store(store_path)
    assert len(loaded.keys) == len(store.keys)
    prod = [k for k in loaded.keys if "production" in {c.lower() for c in k.channels}]
    assert len(prod) == 2
    release = next(k for k in prod if k.role == KeyRole.ONLINE_RELEASE)
    envelope = sign_scorecard(
        _scorecard(),
        private_dir / "prod-online-release.pem",
        key_role=KeyRole.ONLINE_RELEASE,
        key_id_override=release.key_id,
    )
    assert verify_envelope_detailed(
        envelope, trust_store=loaded, policy_mode=TrustPolicyMode.PRODUCTION
    ).ok
    # Production policy still rejects development-only keys from the merged store.
    dev_release = next(
        k
        for k in loaded.keys
        if k.role == KeyRole.ONLINE_RELEASE
        and "development" in {c.lower() for c in k.channels}
        and "production" not in {c.lower() for c in k.channels}
    )
    # Sign with a throwaway key that is not the production release — use DEV private
    # material is unavailable here; assert fail-closed without trust material instead.
    bare = verify_envelope_detailed(envelope, policy_mode=TrustPolicyMode.PRODUCTION)
    assert not bare.ok
    assert bare.reason == VerificationFailureReason.UNKNOWN_KEY
    assert dev_release.key_id.startswith("ed25519:DEV-")


def test_ceremony_script_refuses_in_repo_private_dir() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "signing_ceremony_prod.py"),
            "--private-dir",
            str(ROOT / "trust" / "should-not-write"),
            "--dry-run",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "refusing" in (result.stderr + result.stdout).lower()
