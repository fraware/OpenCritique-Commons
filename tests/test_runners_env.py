"""Env / BYOK contract for live runners (no paid API calls)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from opencritique_runners.env import (
    apply_openai_byok_alias,
    format_live_runner_error,
    load_operator_env,
    redact_secrets,
    require_byok_api_key,
    resolve_byok_api_key,
)


@pytest.fixture(autouse=True)
def _clear_byok_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "OPENCRITIQUE_BYOK_API_KEY",
        "OPENCRITIQUE_BYOK_PROVIDER_ID",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_openai_alias_maps_when_byok_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-alias-only")
    assert resolve_byok_api_key() == "sk-test-alias-only"
    assert os.environ["OPENCRITIQUE_BYOK_API_KEY"] == "sk-test-alias-only"


def test_byok_key_wins_over_openai_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCRITIQUE_BYOK_API_KEY", "sk-byok")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    assert apply_openai_byok_alias() == "sk-byok"


def test_require_byok_fails_closed_without_key() -> None:
    with pytest.raises(RuntimeError, match="OPENCRITIQUE_BYOK_API_KEY"):
        require_byok_api_key()


def test_format_live_runner_error_redacts_and_hints() -> None:
    message = format_live_runner_error(
        RuntimeError("Incorrect API key sk-abcdefghijklmnopqrstuvwxyz012345")
    )
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in message
    assert "[REDACTED]" in message
    assert "docs/deployment-byok.md" in message


def test_redact_secrets_helper() -> None:
    redacted = redact_secrets("OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz")
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "[REDACTED]" in redacted


def test_load_operator_env_does_not_override_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENCRITIQUE_BYOK_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("OPENCRITIQUE_BYOK_API_KEY", "from-process")
    loaded = load_operator_env(dotenv_path=dotenv, override=False)
    # Soft-skip when python-dotenv is absent in the environment.
    if not loaded:
        pytest.skip("python-dotenv not installed")
    assert os.environ["OPENCRITIQUE_BYOK_API_KEY"] == "from-process"
