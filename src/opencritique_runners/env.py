"""Operator env / BYOK contract for live runners.

Load order: process environment wins over optional local ``.env``
(python-dotenv, soft dependency). ``OPENAI_API_KEY`` aliases to
``OPENCRITIQUE_BYOK_API_KEY`` only when the BYOK key is unset.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

BYOK_API_KEY_ENV = "OPENCRITIQUE_BYOK_API_KEY"
BYOK_PROVIDER_ENV = "OPENCRITIQUE_BYOK_PROVIDER_ID"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"

_DEFAULT_PROVIDER = "openai"

_SECRET_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,}|"
    r"(?:OPENAI|OPENROUTER|OPENCRITIQUE_BYOK)_API_KEY\s*[=:]\s*\S+)"
)


def load_operator_env(*, dotenv_path: Path | None = None, override: bool = False) -> bool:
    """Load a local ``.env`` if python-dotenv is installed.

    Returns True when a file was loaded. Existing process env values are kept
    unless ``override`` is True (default False = process env wins).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    path = dotenv_path if dotenv_path is not None else Path.cwd() / ".env"
    if not path.is_file():
        return False
    load_dotenv(dotenv_path=path, override=override)
    return True


def apply_openai_byok_alias() -> str | None:
    """Map ``OPENAI_API_KEY`` → ``OPENCRITIQUE_BYOK_API_KEY`` when BYOK unset.

    Returns the resolved BYOK key (possibly newly aliased), or None.
    Never prints or logs the key material.
    """
    existing = (os.getenv(BYOK_API_KEY_ENV) or "").strip()
    if existing:
        return existing
    alias = (os.getenv(OPENAI_API_KEY_ENV) or "").strip()
    if not alias:
        return None
    os.environ[BYOK_API_KEY_ENV] = alias
    return alias


def resolve_byok_api_key() -> str | None:
    """Return the operator BYOK API key after applying the OpenAI alias."""
    return apply_openai_byok_alias()


def resolve_byok_provider_id(default: str = _DEFAULT_PROVIDER) -> str:
    raw = (os.getenv(BYOK_PROVIDER_ENV) or "").strip()
    return raw or default


def require_byok_api_key() -> str:
    """Fail closed when live commands lack a usable API key."""
    key = resolve_byok_api_key()
    if not key:
        raise RuntimeError(
            "Live Coarse runner requires OPENCRITIQUE_BYOK_API_KEY "
            f"(or {OPENAI_API_KEY_ENV} as alias). Refusing to call paid APIs.\n"
            "Fix:\n"
            '  1. pip install -e ".[live-coarse]"\n'
            "  2. Set OPENCRITIQUE_BYOK_API_KEY in the process env or a local .env "
            "(never commit .env)\n"
            "  3. Optionally set OPENCRITIQUE_BYOK_PROVIDER_ID=openai|openrouter\n"
            "See docs/deployment-byok.md. Default CI must not call paid APIs."
        )
    return key


def redact_secrets(text: str) -> str:
    """Strip key-shaped substrings from operator-facing error text."""
    return _SECRET_RE.sub("[REDACTED]", text)


def format_live_runner_error(exc: BaseException) -> str:
    """Actionable CLI error text without leaking API key material."""
    raw = redact_secrets(str(exc).strip() or exc.__class__.__name__)
    lowered = raw.lower()
    hints: list[str] = []
    if "not installed" in lowered or "no module named 'coarse'" in lowered:
        hints.append('Install the live extra: pip install -e ".[live-coarse]"')
    if "byok" in lowered or "api_key" in lowered or "api key" in lowered:
        hints.append(
            "Set OPENCRITIQUE_BYOK_API_KEY (or OPENAI_API_KEY alias); never print/commit keys."
        )
    if "rate limit" in lowered or "429" in lowered or "too many requests" in lowered:
        hints.append("Provider rate limit: wait and retry, or lower concurrency / model cost.")
    if "model" in lowered and (
        "not found" in lowered or "does not exist" in lowered or "invalid" in lowered
    ):
        hints.append(
            "Check --model (litellm id, e.g. openai/gpt-4o) against your provider account."
        )
    if "auth" in lowered or "401" in lowered or "403" in lowered or "incorrect api" in lowered:
        hints.append(
            "Provider rejected credentials: rotate the key with the provider; "
            "do not paste keys into issues."
        )
    if "openreviewer" in lowered and ("openai" in lowered or "byok" in lowered):
        hints.append(
            "OpenAI/BYOK keys do not run OpenReviewer. Use --from-export or [live-openreviewer]."
        )
    lines = [raw]
    if hints:
        lines.append("Next steps:")
        lines.extend(f"  - {hint}" for hint in hints)
    lines.append("See docs/deployment-byok.md. performance_claims_authorized stays false.")
    return "\n".join(lines)


def prepare_coarse_provider_env(*, provider_id: str | None = None) -> str:
    """Ensure Coarse upstream can see a provider key matching BYOK settings.

    Maps the resolved BYOK key into ``OPENAI_API_KEY`` or ``OPENROUTER_API_KEY``
    when those are unset, based on ``OPENCRITIQUE_BYOK_PROVIDER_ID``.
    """
    key = require_byok_api_key()
    provider = (provider_id or resolve_byok_provider_id()).strip().lower()
    if provider in {"openai", "open-ai"}:
        if not (os.getenv(OPENAI_API_KEY_ENV) or "").strip():
            os.environ[OPENAI_API_KEY_ENV] = key
    elif provider in {"openrouter", "open-router"}:
        if not (os.getenv(OPENROUTER_API_KEY_ENV) or "").strip():
            os.environ[OPENROUTER_API_KEY_ENV] = key
    else:
        # Unknown provider id: still expose OpenAI-style env for litellm defaults.
        if not (os.getenv(OPENAI_API_KEY_ENV) or "").strip():
            os.environ[OPENAI_API_KEY_ENV] = key
    if not (os.getenv(BYOK_PROVIDER_ENV) or "").strip():
        os.environ[BYOK_PROVIDER_ENV] = provider
    return key
