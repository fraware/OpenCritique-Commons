from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


class ArtifactIntegrityError(RuntimeError):
    pass


class LocalArtifactStore:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, sha256: str) -> Path:
        if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
            raise ValueError("invalid SHA-256")
        return self.root / sha256[:2] / sha256[2:4] / sha256

    def put(self, data: bytes) -> tuple[str, Path]:
        self.ensure_root()
        if len(data) > self.max_bytes:
            raise ValueError(f"artifact exceeds configured limit of {self.max_bytes} bytes")
        digest = hashlib.sha256(data).hexdigest()
        target = self.path_for(digest)
        if target.exists():
            if self.read(digest) != data:
                raise ArtifactIntegrityError(
                    "existing content-addressed object has different bytes"
                )
            return digest, target
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".upload-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return digest, target

    def read(self, sha256: str) -> bytes:
        target = self.path_for(sha256)
        data = target.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != sha256:
            raise ArtifactIntegrityError(f"artifact hash mismatch: expected {sha256}, got {actual}")
        return data
