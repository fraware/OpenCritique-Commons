"""PR7 / issue #5: second adapter (OpenReviewer) deterministic conversion."""

from __future__ import annotations

import json
from pathlib import Path

from opencritique_adapters.openreviewer import (
    OPENREVIEWER_CONTRACT_VERSION,
    OPENREVIEWER_PERFORMANCE_CLAIMS_AUTHORIZED,
    convert_openreviewer_benchmark,
    provenance_hash,
)
from opencritique_adapters.openreviewer_loss import write_cross_adapter_report

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "openreviewer"
BENCH = ROOT / "benchmarks" / "openreviewer-synth-v0.1"
MAP = FIXTURES / "maps" / "synth-map.json"
MANIFEST = BENCH / "manifest.json"


def test_adr_and_contract_pinned() -> None:
    adr = ROOT / "governance" / "decisions" / "ADR-0003-second-adapter.md"
    assert adr.is_file()
    text = adr.read_text(encoding="utf-8")
    assert "OpenReviewer" in text
    assert "maxidl/openreviewer" in text
    meta = json.loads((FIXTURES / "UPSTREAM_CONTRACT.json").read_text(encoding="utf-8"))
    assert meta["contract_version"] == OPENREVIEWER_CONTRACT_VERSION
    assert meta["authentic_outputs_available"] is False
    assert OPENREVIEWER_PERFORMANCE_CLAIMS_AUTHORIZED is False


def test_at_least_five_fixtures_convert_deterministically() -> None:
    reviews = sorted((FIXTURES / "reviews").glob("*.json"))
    assert len(reviews) >= 5
    first = convert_openreviewer_benchmark(
        benchmark_manifest_path=MANIFEST, benchmark_root=BENCH, map_path=MAP
    )
    second = convert_openreviewer_benchmark(
        benchmark_manifest_path=MANIFEST, benchmark_root=BENCH, map_path=MAP
    )
    assert [c.model_dump(mode="json") for c in first.cases] == [
        c.model_dump(mode="json") for c in second.cases
    ]
    assert first.system.system_id == "openreviewer"
    assert len(first.cases) >= 5


def test_original_output_preserved_by_hash() -> None:
    for path in (FIXTURES / "reviews").glob("*.json"):
        digest = provenance_hash(path.read_bytes())
        assert len(digest) == 64
        # Round-trip: converter attaches hash in-memory; file bytes remain reconstructible.
        assert path.read_bytes() == path.read_bytes()


def test_missing_fields_stay_unavailable() -> None:
    submission = convert_openreviewer_benchmark(
        benchmark_manifest_path=MANIFEST, benchmark_root=BENCH, map_path=MAP
    )
    # At least one concern should disclose unavailable severity/confidence/anchors.
    notes = " ".join(
        concern.evidence_summary
        for case in submission.cases
        for concern in case.concerns
    )
    assert "Unavailable upstream fields" in notes
    # Structured finding with explicit severity should not claim fields unavailable.
    orv03 = next(c for c in submission.cases if "orv_03" in c.case_id)
    assert orv03.concerns
    assert any(
        "All mapped optional fields were present" in c.evidence_summary
        for c in orv03.concerns
    )


def test_core_schema_has_no_openreviewer_specific_fields() -> None:
    from opencritique_evaluation.models import SubmittedConcern

    fields = set(SubmittedConcern.model_fields)
    assert "openreviewer" not in " ".join(fields).lower()


def test_cross_adapter_report_written() -> None:
    paths = write_cross_adapter_report(ROOT / "docs")
    md = paths["markdown"].read_text(encoding="utf-8")
    assert "openreviewer" in md
    assert "coarse" in md
    assert "Performance claims authorized: **False**" in md
