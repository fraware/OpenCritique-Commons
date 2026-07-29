"""Wave 3: deterministic verifiers with artifact hash binding."""

from __future__ import annotations

from pathlib import Path

from opencritique_ingestion import ingest_path
from opencritique_schema.models import CaseBundle
from opencritique_verification import (
    check_citation_presence,
    check_table_consistency,
    recompute_python,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "corpus" / "samples"


def test_python_recompute_pass_and_reject_import() -> None:
    ok = recompute_python(source="result = abs(-2) + 2", expected=4)
    assert ok.status == "pass"
    assert len(ok.artifact_sha256) == 64
    assert ok.manifest.artifact_sha256 == ok.artifact_sha256
    assert ok.artifacts[0].payload["actual"] == 4
    bad = recompute_python(source="import os\nresult = 1", expected=1)
    assert bad.status == "error"
    assert bad.artifact_sha256
    assert bad.error_kind == "sandbox_error"


def test_table_and_citation_verifiers_on_sample() -> None:
    graph = ingest_path(
        SAMPLES / "sample-figtable-01" / "manuscript.md",
        manuscript_version_id="ocver_verify_fig_v1",
    )
    table = check_table_consistency(
        graph=graph,
        claimed_values={"arm_a": 1.20, "arm_b": 0.85},
    )
    assert table.status == "pass"
    assert table.artifact_sha256
    assert table.details["structural_checks"]
    cites = check_citation_presence(
        graph=graph,
        required_markers=["Smith, A. et al. (2020)"],
    )
    # Bibliography entry text should satisfy the required marker substring.
    assert cites.status == "pass"
    assert cites.artifact_sha256
    assert cites.details["bibliography_entry_count"] == 1


def test_case_evidence_binds_to_deterministic_verifier_artifact() -> None:
    case_path = ROOT / "cases" / "reference" / "REF-02" / "case.json"
    bundle = CaseBundle.model_validate_json(case_path.read_text(encoding="utf-8"))
    manuscript = ROOT / bundle.manuscript_versions[0].source_artifact.uri
    graph = ingest_path(manuscript, manuscript_version_id=bundle.manuscript_versions[0].version_id)
    result = check_table_consistency(graph=graph, claimed_values={"reported_p": 0.05})
    assert result.status == "fail"
    evidence = bundle.evidence[0]
    assert evidence.artifact_reference is not None
    assert (
        evidence.artifact_reference.sha256
        == bundle.manuscript_versions[0].source_artifact.sha256
    )
    assert result.manifest.verifier_id == "table-consistency-v1"
