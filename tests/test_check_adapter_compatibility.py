"""Tests for scripts/check_adapter_compatibility.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_adapter_compatibility.py"


def _load_compat() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_adapter_compatibility", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_compat = _load_compat()
check_path = _compat.check_path
check_registry = _compat.check_registry
main = _compat.main
report_to_markdown = _compat.report_to_markdown


def test_in_tree_coarse_fixtures_pass() -> None:
    report = check_path(ROOT / "fixtures" / "coarse")
    assert report.ok, report_to_markdown([report])


def test_in_tree_openreviewer_fixtures_pass() -> None:
    report = check_path(ROOT / "fixtures" / "openreviewer")
    assert report.ok, report_to_markdown([report])


def test_contract_module_passes() -> None:
    report = check_path(ROOT / "src" / "opencritique_adapters" / "contract.py")
    assert report.ok, report_to_markdown([report])


def test_registry_check_passes() -> None:
    report = check_registry()
    assert report.ok, report_to_markdown([report])


def test_claims_true_fails(tmp_path: Path) -> None:
    contract = tmp_path / "contract.py"
    contract.write_text(
        "EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED = True\n"
        'EXAMPLE_SAMPLE_ADAPTER_CONTRACT_ID = "opencritique-sample-adapter-contract-v1"\n',
        encoding="utf-8",
    )
    report = check_path(contract)
    assert not report.ok
    assert any(item.name == "claims_locked" and not item.passed for item in report.items)


def test_missing_sample_contract_fails(tmp_path: Path) -> None:
    contract = tmp_path / "contract.py"
    contract.write_text(
        "EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED = False\n"
        'EXAMPLE_UPSTREAM_CONTRACT_VERSION = "example-v1"\n',
        encoding="utf-8",
    )
    report = check_path(contract)
    assert not report.ok
    assert any(
        item.name == "sample_contract_present" and not item.passed for item in report.items
    )


def test_fake_production_ready_manifest_refused(tmp_path: Path) -> None:
    prod = tmp_path / "production"
    prod.mkdir()
    manifest = prod / "MANIFEST.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_version": "0.1",
                "adapter": "example",
                "source": "production",
                "status": "ready",
                "upstream_repository": "https://example.invalid/x",
                "upstream_commit_or_config": "opencritique-sample-adapter-contract-v1",
                "rights_record_ids": [],
                "artifacts": [],
                "performance_claims_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    # Also need a sample signal elsewhere so failure is specifically production.
    (tmp_path / "UPSTREAM_CONTRACT.json").write_text(
        json.dumps(
            {
                "performance_claims_authorized": False,
                "sample_adapter_contract_id": "opencritique-sample-adapter-contract-v1",
            }
        ),
        encoding="utf-8",
    )
    report = check_path(tmp_path)
    assert not report.ok
    failed = {item.name: item for item in report.items if not item.passed}
    assert "no_fake_production_ready" in failed


def test_markdown_summary_suitable_for_pr() -> None:
    report = check_path(ROOT / "fixtures" / "coarse")
    md = report_to_markdown([report])
    assert "## Adapter compatibility check" in md
    assert "PASS" in md
    assert "0.5.0a1" in md
    assert "endorsement" in md.lower()


def test_cli_slug_and_registry_exit_zero() -> None:
    code = main(["--slug", "coarse", "--registry"])
    assert code == 0


def test_cli_subprocess_markdown(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("PERFORMANCE_CLAIMS_AUTHORIZED = True\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(bad), "--markdown-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "## Adapter compatibility check" in proc.stdout
    assert "FAIL" in proc.stdout


def test_cli_requires_inputs() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
