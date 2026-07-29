from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from sqlalchemy.engine import make_url

RegistryExecutionMode = Literal["local", "byok", "compose"]

_DEFAULT_DATABASE_URL = "sqlite:///./opencritique.db"
_DEFAULT_ARTIFACT_ROOT = Path("./opencritique-artifacts")
_DEFAULT_MAX_ARTIFACT_BYTES = 50 * 1024 * 1024


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RegistrySettings:
    database_url: str = _DEFAULT_DATABASE_URL
    artifact_root: Path = _DEFAULT_ARTIFACT_ROOT
    max_artifact_bytes: int = _DEFAULT_MAX_ARTIFACT_BYTES
    execution_mode: RegistryExecutionMode = "local"
    byok_provider_id: str | None = None
    performance_claims_authorized: bool = False

    @classmethod
    def from_env(cls) -> RegistrySettings:
        raw_bytes = os.getenv(
            "OPENCRITIQUE_MAX_ARTIFACT_BYTES",
            str(_DEFAULT_MAX_ARTIFACT_BYTES),
        )
        try:
            max_artifact_bytes = int(raw_bytes)
        except ValueError as exc:
            raise ValueError("OPENCRITIQUE_MAX_ARTIFACT_BYTES must be an integer") from exc
        return cls(
            database_url=os.getenv("OPENCRITIQUE_DATABASE_URL", _DEFAULT_DATABASE_URL),
            artifact_root=Path(
                os.getenv(
                    "OPENCRITIQUE_ARTIFACT_ROOT",
                    str(_DEFAULT_ARTIFACT_ROOT),
                )
            ),
            max_artifact_bytes=max_artifact_bytes,
            execution_mode=os.getenv("OPENCRITIQUE_EXECUTION_MODE", "local")
            .strip()
            .lower(),  # type: ignore[arg-type]
            byok_provider_id=os.getenv("OPENCRITIQUE_BYOK_PROVIDER_ID"),
            performance_claims_authorized=_env_flag(
                "OPENCRITIQUE_PERFORMANCE_CLAIMS_AUTHORIZED",
                default=False,
            ),
        ).validated()

    def with_overrides(
        self,
        *,
        database_url: str | None = None,
        artifact_root: Path | None = None,
        max_artifact_bytes: int | None = None,
        execution_mode: RegistryExecutionMode | None = None,
    ) -> RegistrySettings:
        return replace(
            self,
            database_url=database_url or self.database_url,
            artifact_root=artifact_root or self.artifact_root,
            max_artifact_bytes=max_artifact_bytes or self.max_artifact_bytes,
            execution_mode=execution_mode or self.execution_mode,
        ).validated()

    def validated(self) -> RegistrySettings:
        if self.execution_mode not in {"local", "byok", "compose"}:
            raise ValueError(
                "OPENCRITIQUE_EXECUTION_MODE must be one of: local, byok, compose"
            )
        if self.max_artifact_bytes <= 0:
            raise ValueError(
                "OPENCRITIQUE_MAX_ARTIFACT_BYTES must be greater than zero"
            )
        self._validate_database_url()
        normalized_root = self._validate_artifact_root()
        if self.execution_mode == "byok":
            if not (self.byok_provider_id or "").strip():
                raise ValueError(
                    "BYOK mode requires OPENCRITIQUE_BYOK_PROVIDER_ID to be set"
                )
            if not (os.getenv("OPENCRITIQUE_BYOK_API_KEY", "")).strip():
                raise ValueError(
                    "BYOK mode requires OPENCRITIQUE_BYOK_API_KEY to be set"
                )
        if self.performance_claims_authorized:
            raise ValueError(
                "OPENCRITIQUE_PERFORMANCE_CLAIMS_AUTHORIZED must remain false "
                "for this release"
            )
        return replace(self, artifact_root=normalized_root)

    def _validate_database_url(self) -> None:
        try:
            url = make_url(self.database_url)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"invalid OPENCRITIQUE_DATABASE_URL: {exc}") from exc
        if url.drivername not in {"sqlite", "postgresql+psycopg", "postgresql"}:
            raise ValueError(
                "OPENCRITIQUE_DATABASE_URL must use sqlite or postgresql+psycopg"
            )
        if url.drivername == "sqlite" and not (url.database or "").strip():
            raise ValueError(
                "sqlite OPENCRITIQUE_DATABASE_URL must include a database path"
            )

    def _validate_artifact_root(self) -> Path:
        root = self.artifact_root.expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise ValueError("OPENCRITIQUE_ARTIFACT_ROOT must be a directory path")
        probe_root = root if root.exists() else root.parent
        if not probe_root.exists():
            probe_root.mkdir(parents=True, exist_ok=True)
        if not probe_root.is_dir():
            raise ValueError("OPENCRITIQUE_ARTIFACT_ROOT parent must be a directory")
        try:
            with NamedTemporaryFile(
                dir=probe_root,
                prefix=".oc-config-",
                delete=True,
            ):
                pass
        except OSError as exc:
            raise ValueError(
                f"OPENCRITIQUE_ARTIFACT_ROOT is not writable via {probe_root}: {exc}"
            ) from exc
        return root
