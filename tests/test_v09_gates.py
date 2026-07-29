"""v0.9-beta machine-checkable go/no-go gates."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_gates():
    import sys

    name = "check_v09_gates"
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / "scripts" / "check_v09_gates.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_v09_gates_are_no_go() -> None:
    module = _load_gates()
    results = module.evaluate_gates()
    by_id = {item.gate_id: item for item in results}
    assert by_id[2].passed is False
    assert by_id[3].passed is False
    assert by_id[6].passed is False
    assert by_id[9].passed is True  # claims remain locked
    assert module.main() == 1


def test_v09_doc_references_machine_check() -> None:
    text = (ROOT / "docs" / "v0.9-beta-go-no-go.md").read_text(encoding="utf-8")
    assert "check_v09_gates.py" in text
    assert "performance_claims_authorized" in text
