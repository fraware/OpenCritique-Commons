"""Wave 3: acquisition import / withdraw / cancel CLI paths."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from opencritique_acquisition.cli import app
from opencritique_acquisition.models import AcquisitionStatus, load_ledger


def test_import_withdraw_cancel_roundtrip(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    runner = CliRunner()
    imported = runner.invoke(
        app,
        [
            "import-source",
            str(ledger_path),
            "--source-id",
            "sample-test-source",
            "--title",
            "Temporary sample source",
            "--paper-url",
            "https://example.com/sample",
            "--declared-license",
            "Apache-2.0",
            "--license-evidence-url",
            "https://example.com/license",
            "--imported-case-count",
            "1",
            "--grant-authority",
            "test-maintainer",
            "--grant-scope",
            "sample conformance only",
            "--note",
            "temporary",
        ],
    )
    assert imported.exit_code == 0, imported.stdout + imported.stderr
    ledger = load_ledger(ledger_path)
    assert ledger.total_imported_cases == 1
    assert ledger.sources[0].status == AcquisitionStatus.IMPORTED
    assert ledger.sources[0].grant_authority == "test-maintainer"

    withdrawn = runner.invoke(
        app,
        [
            "withdraw",
            str(ledger_path),
            "--source-id",
            "sample-test-source",
            "--reason",
            "author request",
        ],
    )
    assert withdrawn.exit_code == 0, withdrawn.stdout + withdrawn.stderr
    ledger = load_ledger(ledger_path)
    assert ledger.total_imported_cases == 0
    assert ledger.sources[0].status == AcquisitionStatus.WITHDRAWN

    # Re-import under a new id then cancel.
    runner.invoke(
        app,
        [
            "import-source",
            str(ledger_path),
            "--source-id",
            "sample-test-source-2",
            "--title",
            "Another sample",
            "--paper-url",
            "https://example.com/sample2",
            "--declared-license",
            "Apache-2.0",
            "--license-evidence-url",
            "https://example.com/license",
            "--imported-case-count",
            "2",
            "--grant-authority",
            "test-maintainer",
            "--grant-scope",
            "sample conformance only",
        ],
    )
    cancelled = runner.invoke(
        app,
        [
            "cancel",
            str(ledger_path),
            "--source-id",
            "sample-test-source-2",
            "--reason",
            "pipeline abort",
        ],
    )
    assert cancelled.exit_code == 0, cancelled.stdout + cancelled.stderr
    ledger = load_ledger(ledger_path)
    assert any(s.status == AcquisitionStatus.CANCELLED for s in ledger.sources)
    assert ledger.performance_claims_authorized is False
