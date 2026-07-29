"""BYOK SystemManifest fail-closed retention tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from opencritique_evaluation.models import ByokConfig, SystemManifest


def _base(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "system_id": "byok-system",
        "version": "0.1.0",
        "display_name": "BYOK System",
        "configuration_hash": "a" * 64,
        "execution_mode": "byok",
        "byok": {"provider_id": "openai-compatible", "retain_credentials": False},
    }
    payload.update(overrides)
    return payload


def test_byok_manifest_accepts_provider_without_secrets() -> None:
    manifest = SystemManifest.model_validate(_base())
    assert manifest.execution_mode == "byok"
    assert manifest.byok is not None
    assert manifest.byok.provider_id == "openai-compatible"
    assert manifest.byok.retain_credentials is False


def test_byok_rejects_credential_retention() -> None:
    with pytest.raises(ValidationError):
        ByokConfig.model_validate({"provider_id": "x", "retain_credentials": True})


def test_byok_rejects_secret_fields() -> None:
    for banned in (
        {"provider_id": "x", "api_key": "sk-test"},
        {"provider_id": "x", "credential_reference": "vault://secret"},
        {"provider_id": "x", "token": "abc"},
        {"provider_id": "x", "password": "secret"},
    ):
        with pytest.raises(ValidationError):
            ByokConfig.model_validate(banned)


def test_byok_mode_requires_config() -> None:
    with pytest.raises(ValidationError):
        SystemManifest.model_validate(
            {
                "system_id": "byok-system",
                "version": "0.1.0",
                "display_name": "BYOK System",
                "configuration_hash": "a" * 64,
                "execution_mode": "byok",
            }
        )


def test_byok_config_forbidden_outside_byok_mode() -> None:
    with pytest.raises(ValidationError):
        SystemManifest.model_validate(
            {
                "system_id": "local-system",
                "version": "0.1.0",
                "display_name": "Local",
                "configuration_hash": "a" * 64,
                "execution_mode": "local",
                "byok": {"provider_id": "x"},
            }
        )
