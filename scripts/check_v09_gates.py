#!/usr/bin/env python3
"""Machine-checkable v0.9-beta go/no-go gate evaluator.

Exits non-zero while critical authenticity gates remain unmet.
Does not unlock performance claims.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opencritique_adapters.production_fixtures import (  # noqa: E402
    COARSE_PRODUCTION,
    OPENREVIEWER_PRODUCTION,
    ProductionIntakeStatus,
    load_production_manifest,
    production_section_for,
)
from opencritique_evaluation.matcher_audit import measure_current_denominators  # noqa: E402
from opencritique_registry.expert_policy import (  # noqa: E402
    assert_calibration_seeds_resolvable,
    load_attribution_policy,
    load_calibration_seeds_policy,
    load_compensation_policy,
    load_qualification_policy,
)


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: int
    name: str
    passed: bool
    blocking: bool
    detail: str


def _gate_production(adapter: str, root: Path, gate_id: int, name: str) -> GateResult:
    try:
        section = production_section_for(adapter, root)
        manifest = load_production_manifest(root / "MANIFEST.json")
    except Exception as exc:  # noqa: BLE001
        return GateResult(gate_id, name, False, True, f"error: {exc}")
    ready = (
        section.status == ProductionIntakeStatus.READY
        and section.export_count > 0
        and manifest.performance_claims_authorized is False
    )
    return GateResult(
        gate_id,
        name,
        ready,
        True,
        f"status={section.status.value} exports={section.export_count}",
    )


def evaluate_gates() -> list[GateResult]:
    results: list[GateResult] = []

    rights_status = ROOT / "docs" / "rights-clearance-status.md"
    results.append(
        GateResult(
            1,
            "external_rights_path_or_negative_finding",
            rights_status.is_file()
            and "negative finding" in rights_status.read_text(encoding="utf-8").lower(),
            False,  # archived negative finding satisfies process; natural import still open
            "negative finding archived; natural import still blocked",
        )
    )

    results.append(
        _gate_production("coarse", COARSE_PRODUCTION, 2, "coarse_production_fixtures")
    )
    results.append(
        _gate_production(
            "openreviewer",
            OPENREVIEWER_PRODUCTION,
            3,
            "openreviewer_production_fixtures",
        )
    )

    trust = ROOT / "trust" / "scorecard-trust-store.json"
    prod_keys_ok = False
    if trust.is_file():
        raw = trust.read_text(encoding="utf-8")
        prod_keys_ok = "PROD-ROOT" in raw or "PROD-RELEASE" in raw
    results.append(
        GateResult(
            4,
            "production_signing_public_keys",
            prod_keys_ok,
            False,
            "production public keys present; private keys must stay offline",
        )
    )

    try:
        load_qualification_policy()
        load_compensation_policy()
        load_attribution_policy()
        load_calibration_seeds_policy()
        assert_calibration_seeds_resolvable()
        expert_ok = True
        expert_detail = "policy objects load; calibration seeds resolve"
    except Exception as exc:  # noqa: BLE001
        expert_ok = False
        expert_detail = str(exc)
    results.append(
        GateResult(5, "expert_ops_policy_objects", expert_ok, False, expert_detail)
    )

    denominators = measure_current_denominators(natural_decision_count=0, repo_root=ROOT)
    results.append(
        GateResult(
            6,
            "matcher_audit_natural_volume",
            denominators.natural_dod_met,
            True,
            (
                f"natural={denominators.natural_decisions_available} "
                f"sample_fixture_reviews={denominators.sample_decisions_available} "
                f"dod_met={denominators.natural_dod_met}"
            ),
        )
    )

    results.append(
        GateResult(
            7,
            "two_domain_natural_adjudication_staffing",
            False,
            True,
            "natural holdout staffing not met",
        )
    )

    results.append(
        GateResult(
            8,
            "holdout_custody_documented",
            (ROOT / "docs" / "matcher-audit-protocol.md").is_file(),
            False,
            "engineering docs present; natural holdout missing",
        )
    )

    claims_locked = True
    for path in (
        ROOT / "corpus" / "acquisition-ledger.json",
        COARSE_PRODUCTION / "MANIFEST.json",
        OPENREVIEWER_PRODUCTION / "MANIFEST.json",
    ):
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("performance_claims_authorized") is True:
                claims_locked = False
    results.append(
        GateResult(
            9,
            "performance_claims_locked",
            claims_locked,
            True,
            "performance_claims_authorized must remain false",
        )
    )

    results.append(
        GateResult(
            10,
            "v09_checklist_document",
            (ROOT / "docs" / "v0.9-beta-go-no-go.md").is_file(),
            False,
            "checklist document present",
        )
    )
    return results


def main() -> int:
    results = evaluate_gates()
    blocking_failures = [item for item in results if item.blocking and not item.passed]
    print("v0.9-beta go/no-go machine check")
    print("performance_claims_authorized=false (enforced)")
    for item in results:
        mark = "PASS" if item.passed else "FAIL"
        block = "blocking" if item.blocking else "informational"
        print(f"  [{mark}] #{item.gate_id} {item.name} ({block}): {item.detail}")
    if blocking_failures:
        print(
            f"NO-GO: {len(blocking_failures)} blocking gate(s) unmet; "
            "do not cut v0.9-beta claim surfaces."
        )
        return 1
    print("GO: blocking authenticity gates met (claims remain locked separately).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
