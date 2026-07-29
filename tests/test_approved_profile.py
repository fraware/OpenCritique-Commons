"""Approved-profile natural/sample intake (post-#7 path)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from opencritique_acquisition.approved_profile import (
    ApprovedProfileError,
    SourceProfileKind,
    import_approved_profile,
    load_approved_profile,
    parse_approved_profile,
    reject_outside_approved_profile,
)
from opencritique_acquisition.cli import app as acquisition_app

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "corpus" / "samples" / "sample-econ-01" / "manuscript.md"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sample_profile(tmp_path: Path) -> Path:
    profile = {
        "profile_version": "0.1",
        "profile_kind": "sample",
        "source_id": "test-sample-profile-01",
        "title": "Sample profile conformance",
        "paper_url": "https://example.invalid/sample",
        "declared_license": "Apache-2.0",
        "license_evidence_url": "https://example.invalid/license",
        "grant_authority": "OpenCritique maintainers",
        "grant_scope": "maintainer-owned sample evaluation use",
        "evaluation_use_authorized": True,
        "redistribution_authorized": True,
        "natural_manuscript_imported": False,
        "performance_claims_authorized": False,
        "case_id": "occase_rights_rc_01",
        "case_version": "1.0.0",
        "manuscript_path": "corpus/samples/sample-econ-01/manuscript.md",
        "source_artifact_sha256": _digest(SAMPLES),
        "rights_record_path": "corpus/rights/rc-01.json",
        "notes": ["conformance only"],
    }
    path = tmp_path / "sample-profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    return path


def test_sample_profile_validates() -> None:
    profile = parse_approved_profile(
        {
            "profile_kind": "sample",
            "source_id": "s1",
            "title": "t",
            "paper_url": "https://example.invalid/p",
            "declared_license": "Apache-2.0",
            "license_evidence_url": "https://example.invalid/l",
            "grant_authority": "maintainers",
            "grant_scope": "sample evaluation",
            "evaluation_use_authorized": True,
            "redistribution_authorized": True,
            "natural_manuscript_imported": False,
            "case_id": "occase_rights_rc_01",
            "case_version": "1.0.0",
            "manuscript_path": "corpus/samples/sample-econ-01/manuscript.md",
            "source_artifact_sha256": _digest(SAMPLES),
            "rights_record_path": "corpus/rights/rc-01.json",
        }
    )
    reject_outside_approved_profile(profile, ROOT)


def test_reject_sample_claiming_natural() -> None:
    with pytest.raises(ApprovedProfileError) as exc:
        parse_approved_profile(
            {
                "profile_kind": "sample",
                "source_id": "s1",
                "title": "t",
                "paper_url": "https://example.invalid/p",
                "declared_license": "Apache-2.0",
                "license_evidence_url": "https://example.invalid/l",
                "grant_authority": "maintainers",
                "grant_scope": "sample evaluation",
                "evaluation_use_authorized": True,
                "redistribution_authorized": True,
                "natural_manuscript_imported": True,
                "case_id": "c1",
                "case_version": "1",
                "manuscript_path": "x.md",
                "source_artifact_sha256": "0" * 64,
            }
        )
    assert exc.value.code == "sample_natural_contamination"


def test_reject_natural_public_availability_scope() -> None:
    with pytest.raises(ApprovedProfileError) as exc:
        parse_approved_profile(
            {
                "profile_kind": "natural",
                "source_id": "n1",
                "title": "t",
                "paper_url": "https://example.invalid/p",
                "declared_license": "CC-BY-4.0",
                "license_evidence_url": "https://example.invalid/l",
                "grant_authority": "owner",
                "grant_scope": "public availability of PDF",
                "evaluation_use_authorized": True,
                "redistribution_authorized": True,
                "natural_manuscript_imported": True,
                "case_id": "c1",
                "case_version": "1",
                "manuscript_path": "x.md",
                "source_artifact_sha256": "0" * 64,
                "rights_record_path": "corpus/rights/rc-01.json",
            }
        )
    assert exc.value.code == "public_availability_insufficient"


def test_reject_hash_mismatch(tmp_path: Path) -> None:
    path = _sample_profile(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["source_artifact_sha256"] = "ab" * 32
    path.write_text(json.dumps(data), encoding="utf-8")
    profile = load_approved_profile(path)
    with pytest.raises(ApprovedProfileError) as exc:
        reject_outside_approved_profile(profile, ROOT)
    assert exc.value.code == "hash_mismatch"


def test_dry_run_import_sample_profile(tmp_path: Path) -> None:
    profile_path = _sample_profile(tmp_path)
    profile = load_approved_profile(profile_path)
    ledger_path = tmp_path / "ledger.json"
    updated = import_approved_profile(
        profile,
        ledger_path=ledger_path,
        repo_root=ROOT,
        dry_run=True,
    )
    assert updated.total_imported_cases == 0
    assert not ledger_path.exists()
    assert profile.profile_kind == SourceProfileKind.SAMPLE


def test_cli_validate_approved_profile(tmp_path: Path) -> None:
    profile_path = _sample_profile(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        acquisition_app,
        ["validate-approved-profile", str(profile_path), "--repo-root", str(ROOT)],
    )
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


def test_rights_memorandum_documents_command_sequence() -> None:
    text = (ROOT / "docs" / "rights-memorandum.md").read_text(encoding="utf-8")
    assert "import-approved-profile" in text
    assert "validate-approved-profile" in text
    assert "performance_claims_authorized" in text
