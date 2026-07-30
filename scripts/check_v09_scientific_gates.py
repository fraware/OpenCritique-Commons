#!/usr/bin/env python3
"""v0.9 scientific authenticity gate evaluator.

Exits non-zero while consequential scientific authenticity gates remain unmet.
Does not unlock performance claims.

Blocking failures require verified ``SignedEvidenceEnvelope`` artifacts under
``governance/evidence/attestations/`` (or explicit ``missing_attestation`` /
signature / binding failure reasons). Boolean JSON, roster flags, ledger counts,
and MANIFEST presence alone never invent a PASS or set
``performance_claims_authorized=true``.

Scientific blockers:
  natural rights-cleared cases; authentic reviewer outputs; qualified expert
  staffing; holdout custody; matcher audit; independent evaluation; production
  signing; claims lock.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from v09_gate_lib import (  # noqa: E402
    COARSE_PRODUCTION,
    OPENREVIEWER_PRODUCTION,
    GateResult,
    gate_holdout_custody_scientific,
    gate_independent_evaluation,
    gate_matcher_audit,
    gate_natural_rights_cleared,
    gate_performance_claims_locked,
    gate_production,
    gate_production_signing,
    gate_staffing,
    report_gates,
)


def evaluate_scientific_gates() -> list[GateResult]:
    return [
        gate_natural_rights_cleared(1, blocking=True),
        gate_production("coarse", COARSE_PRODUCTION, 2, "coarse_production_fixtures"),
        gate_production(
            "openreviewer",
            OPENREVIEWER_PRODUCTION,
            3,
            "openreviewer_production_fixtures",
        ),
        gate_production_signing(4, blocking=True),
        gate_staffing(5, blocking=True),
        gate_matcher_audit(6, blocking=True),
        gate_holdout_custody_scientific(7, blocking=True),
        gate_independent_evaluation(8, blocking=True),
        gate_performance_claims_locked(9, blocking=True),
    ]


def evaluate_gates() -> list[GateResult]:
    """Alias for callers/tests expecting evaluate_gates()."""
    return evaluate_scientific_gates()


def main() -> int:
    return report_gates(
        "v0.9-beta scientific authenticity gate check",
        evaluate_scientific_gates(),
        go_message=(
            "GO: blocking scientific authenticity gates met "
            "(claims remain locked separately)."
        ),
        no_go_message=(
            "NO-GO: {count} blocking scientific gate(s) unmet; "
            "do not cut v0.9-beta claim surfaces."
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
