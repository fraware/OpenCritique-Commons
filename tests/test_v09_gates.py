"""v0.9-beta machine-checkable go/no-go gates (engineering vs scientific)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    import sys

    path = ROOT / "scripts" / name
    module_name = path.stem
    # Ensure sibling imports (v09_gate_lib) resolve when loading by path.
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_scientific_gates_are_no_go() -> None:
    module = _load_script("check_v09_scientific_gates.py")
    results = module.evaluate_scientific_gates()
    by_name = {item.name: item for item in results}
    assert by_name["natural_rights_cleared_cases"].passed is False
    assert by_name["natural_rights_cleared_cases"].blocking is True
    assert "missing_attestation" in by_name["natural_rights_cleared_cases"].detail
    assert by_name["coarse_production_fixtures"].passed is False
    assert "missing_attestation" in by_name["coarse_production_fixtures"].detail
    assert by_name["openreviewer_production_fixtures"].passed is False
    assert "missing_attestation" in by_name["openreviewer_production_fixtures"].detail
    assert by_name["production_signing_public_keys"].passed is True
    assert by_name["production_signing_public_keys"].blocking is True
    assert by_name["qualified_expert_staffing"].passed is False
    assert "missing_attestation" in by_name["qualified_expert_staffing"].detail
    assert by_name["matcher_audit_natural_volume"].passed is False
    assert "missing_attestation" in by_name["matcher_audit_natural_volume"].detail
    assert by_name["holdout_custody"].passed is False
    assert by_name["holdout_custody"].blocking is True
    assert "missing_attestation" in by_name["holdout_custody"].detail
    assert by_name["independent_evaluation"].passed is False
    assert by_name["independent_evaluation"].blocking is True
    assert "missing_attestation" in by_name["independent_evaluation"].detail
    assert by_name["performance_claims_locked"].passed is True
    assert "evidence" in by_name["matcher_audit_natural_volume"].detail or (
        "sessions" in by_name["matcher_audit_natural_volume"].detail
    )
    assert "natural-adjudication-staffing.json" in by_name["qualified_expert_staffing"].detail
    assert by_name["natural_rights_cleared_cases"].verification_report is not None
    assert (
        by_name["natural_rights_cleared_cases"].verification_report["reason"]
        == "missing_attestation"
    )
    assert module.main() == 1


def test_engineering_gates_are_scaffolding_ok() -> None:
    module = _load_script("check_v09_engineering_gates.py")
    results = module.evaluate_engineering_gates()
    assert all(not item.blocking for item in results)
    by_name = {item.name: item for item in results}
    assert by_name["external_rights_path_or_negative_finding"].passed is True
    assert by_name["production_signing_public_keys"].passed is True
    assert by_name["expert_ops_policy_objects"].passed is True
    assert by_name["holdout_custody_documented"].passed is True
    assert by_name["v09_checklist_document"].passed is True
    assert module.main() == 0


def test_scientific_gates_point_at_evidence_paths() -> None:
    module = _load_script("check_v09_scientific_gates.py")
    results = module.evaluate_scientific_gates()
    by_name = {item.name: item for item in results}
    assert "reviewer-export-coarse.envelope.json" in by_name[
        "coarse_production_fixtures"
    ].detail
    assert "reviewer-export-openreviewer.envelope.json" in by_name[
        "openreviewer_production_fixtures"
    ].detail
    assert "matcher-audit-completion.envelope.json" in by_name[
        "matcher_audit_natural_volume"
    ].detail
    staffing = ROOT / "governance" / "evidence" / "natural-adjudication-staffing.json"
    roster = json.loads(staffing.read_text(encoding="utf-8"))
    assert roster["status"] == "blocked"
    assert roster["performance_claims_authorized"] is False
    assert roster["domains"] == []
    placeholder = (
        ROOT
        / "governance"
        / "evidence"
        / "attestations"
        / "natural-corpus.placeholder.json"
    )
    assert placeholder.is_file()
    assert not (
        ROOT / "governance" / "evidence" / "attestations" / "natural-corpus.envelope.json"
    ).is_file()
    payload = json.loads(placeholder.read_text(encoding="utf-8"))
    assert payload["verification_status"] == "blocked"

def test_compat_orchestrator_follows_scientific_exit() -> None:
    module = _load_script("check_v09_gates.py")
    assert module.main() == 1


def test_v09_doc_references_split_machine_checks() -> None:
    text = (ROOT / "docs" / "v0.9-beta-go-no-go.md").read_text(encoding="utf-8")
    assert "check_v09_scientific_gates.py" in text
    assert "check_v09_engineering_gates.py" in text
    assert "performance_claims_authorized" in text
    assert "exits 0" in text or "exit 0" in text
    milestones = (ROOT / "docs" / "MILESTONES.md").read_text(encoding="utf-8")
    assert "check_v09_scientific_gates.py" in milestones
    assert "GO rule" in milestones
    assert "claims stay" in milestones and "locked" in milestones
