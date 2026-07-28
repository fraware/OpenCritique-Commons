"""Release packaging and distribution smoke tests."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = [
    "opencritique_schema",
    "opencritique_registry",
    "opencritique_evaluation",
    "opencritique_adapters",
    "opencritique_acquisition",
]


def test_build_release_manifest_script(tmp_path) -> None:
    script = ROOT / "scripts" / "build_release_manifest.py"
    out = tmp_path / "dist"
    out.mkdir()
    # Create a fake wheel for checksum coverage.
    fake = out / "opencritique_commons-0.5.0a1-py3-none-any.whl"
    fake.write_bytes(b"PK\x03\x04fake-wheel")
    subprocess.check_call([sys.executable, str(script), str(out)])
    assert (out / "RELEASE_MANIFEST.json").is_file()
    assert (out / "SHA256SUMS").is_file()
    assert (out / "sbom.cdx.json").is_file()


def test_secret_scan_script_passes() -> None:
    script = ROOT / "scripts" / "secret_scan.py"
    subprocess.check_call([sys.executable, str(script)], cwd=ROOT)


def test_editable_packages_importable() -> None:
    for name in PACKAGES:
        module = importlib.import_module(name)
        assert module is not None
