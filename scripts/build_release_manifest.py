#!/usr/bin/env python3
"""Build release manifest, checksums, and a minimal CycloneDX-like SBOM."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = [
    "opencritique_schema",
    "opencritique_registry",
    "opencritique_evaluation",
    "opencritique_adapters",
    "opencritique_acquisition",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_version() -> str:
    try:
        return version("opencritique-commons")
    except PackageNotFoundError:
        return "0.5.0a1"


def main(dist_dir: Path | None = None, out_dir: Path | None = None) -> int:
    dist_dir = dist_dir or (ROOT / "dist")
    out_dir = out_dir or (ROOT / "dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict] = []
    if dist_dir.is_dir():
        for path in sorted(dist_dir.iterdir()):
            if path.suffix in {".whl", ".gz"} or path.name.endswith(".tar.gz"):
                artifacts.append(
                    {
                        "path": path.name,
                        "sha256": _sha256(path),
                        "bytes": path.stat().st_size,
                    }
                )
    release = {
        "name": "opencritique-commons",
        "version": _project_version(),
        "generated_at": datetime.now(UTC).isoformat(),
        "packages": PACKAGES,
        "artifacts": artifacts,
        "schema_freeze_release": "0.5.0a1",
        "notes": [
            "No scientific performance claims are authorized by this release artifact.",
            "SBOM lists runtime package identity; dependency components are declared below.",
        ],
    }
    runtime_deps = [
        "pydantic",
        "typer",
        "fastapi",
        "sqlalchemy",
        "alembic",
        "uvicorn",
        "cryptography",
    ]
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": release["generated_at"],
            "component": {
                "type": "library",
                "name": "opencritique-commons",
                "version": release["version"],
            },
        },
        "components": [
            {
                "type": "library",
                "name": dep,
                "version": _safe_version(dep),
            }
            for dep in runtime_deps
        ],
    }
    manifest_path = out_dir / "RELEASE_MANIFEST.json"
    checksums_path = out_dir / "SHA256SUMS"
    sbom_path = out_dir / "sbom.cdx.json"
    manifest_path.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_lines = [f"{item['sha256']}  {item['path']}" for item in artifacts]
    checksum_lines.append(f"{_sha256(manifest_path)}  {manifest_path.name}")
    checksums_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    sbom_path.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(manifest_path)
    print(checksums_path)
    print(sbom_path)
    return 0


def _safe_version(dist_name: str) -> str:
    try:
        return version(dist_name)
    except PackageNotFoundError:
        return "unknown"


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    raise SystemExit(main(dist_dir=target, out_dir=target))
