from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RegistrySettings:
    database_url: str = "sqlite:///./opencritique.db"
    artifact_root: Path = Path("./opencritique-artifacts")
    max_artifact_bytes: int = 50 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "RegistrySettings":
        return cls(
            database_url=os.getenv("OPENCRITIQUE_DATABASE_URL", cls.database_url),
            artifact_root=Path(os.getenv("OPENCRITIQUE_ARTIFACT_ROOT", str(cls.artifact_root))),
            max_artifact_bytes=int(
                os.getenv("OPENCRITIQUE_MAX_ARTIFACT_BYTES", str(cls.max_artifact_bytes))
            ),
        )
