"""PR10 / issue #7: first rights path with six candidate cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from opencritique_acquisition.models import AcquisitionLedger, AcquisitionSource, AcquisitionStatus
from opencritique_schema.models import CaseBundle

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases" / "rights-candidates"
RIGHTS = ROOT / "corpus" / "rights"
LEDGER = ROOT / "corpus" / "acquisition-ledger.json"
MEMO = ROOT / "docs" / "rights-memorandum.md"


def test_rights_memorandum_and_claim_boundary() -> None:
    text = MEMO.read_text(encoding="utf-8")
    assert "not" in text.lower() and "authorization" in text.lower()
    assert "performance_claims_authorized" in text
    assert "PeerQA" in text


def test_six_candidate_cases_with_rights_records() -> None:
    case_dirs = sorted(p for p in CASES.iterdir() if p.is_dir())
    assert len(case_dirs) >= 6
    for path in case_dirs:
        bundle = CaseBundle.model_validate_json((path / "case.json").read_text(encoding="utf-8"))
        assert "[SYNTHETIC]" in (bundle.manuscript.title or "")
        rights_path = RIGHTS / f"{path.name}.json"
        assert rights_path.is_file()
        rights = json.loads(rights_path.read_text(encoding="utf-8"))
        assert rights["case_id"] == bundle.case_id
        assert rights["evaluation_use_authorized"] is True
        assert rights["source_artifact_sha256"]
        assert rights["performance_claims_authorized"] is False
        assert rights["synthetic_placeholder"] is True


def test_acquisition_ledger_disables_performance_claims() -> None:
    ledger = AcquisitionLedger.model_validate_json(LEDGER.read_text(encoding="utf-8"))
    assert ledger.total_imported_cases == 6
    assert ledger.performance_claims_authorized is False
    imported = [s for s in ledger.sources if s.status == AcquisitionStatus.IMPORTED]
    assert all(s.evaluation_use_authorized for s in imported)


def test_import_tooling_rejects_unauthorized_import() -> None:
    with pytest.raises(ValidationError):
        AcquisitionSource(
            source_id="bad",
            title="Uncleared public PDF",
            paper_url="https://example.com/paper.pdf",
            status=AcquisitionStatus.IMPORTED,
            evaluation_use_authorized=False,
            imported_case_count=1,
        )


def test_readme_has_no_performance_claims() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    banned = ["precision=", "recall=", "f1=", "outperforms", "state-of-the-art reviewer"]
    for phrase in banned:
        assert phrase not in readme
