#!/usr/bin/env python3
"""v0.9 engineering gate evaluator (scaffolding / process).

Informational by design: consequential scientific authenticity lives in
``check_v09_scientific_gates.py``. This script confirms engineering process
artifacts (rights negative-finding archive, expert policy objects, holdout
docs, checklist, production public keys) without unlocking claims.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from v09_gate_lib import (  # noqa: E402
    GateResult,
    gate_checklist_document,
    gate_expert_ops_policy,
    gate_holdout_custody_documented,
    gate_production_signing,
    gate_rights_process_or_negative_finding,
    report_gates,
)


def evaluate_engineering_gates() -> list[GateResult]:
    return [
        gate_rights_process_or_negative_finding(1, blocking=False),
        gate_production_signing(2, blocking=False),
        gate_expert_ops_policy(3, blocking=False),
        gate_holdout_custody_documented(4, blocking=False),
        gate_checklist_document(5, blocking=False),
    ]


def main() -> int:
    return report_gates(
        "v0.9-beta engineering gate check",
        evaluate_engineering_gates(),
        go_message=(
            "ENGINEERING OK: process scaffolding present "
            "(scientific authenticity checked separately)."
        ),
        no_go_message=(
            "ENGINEERING NO-GO: {count} blocking engineering gate(s) unmet."
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
