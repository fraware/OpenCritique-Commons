#!/usr/bin/env python3
"""Machine-checkable v0.9-beta go/no-go gate evaluator.

Exits non-zero while critical authenticity gates remain unmet.
Does not unlock performance claims.

Blocking failures point at missing or blocked **evidence artifacts**
(session manifests, staffing roster, production MANIFESTs) — never invents
counts or sets ``performance_claims_authorized=true``.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opencritique_adapters.production_fixtures import (  # noqa: E402
    ADAPTER_READY_MINIMA,
    COARSE_PRODUCTION,
    OPENREVIEWER_PRODUCTION,
    ProductionIntakeStatus,
    load_production_manifest,
    production_section_for,
)
from opencritique_evaluation.matcher_audit import (  # noqa: E402
    discover_natural_decision_count,
    measure_current_denominators,
    natural_session_manifest_dir,
)
from opencritique_registry.expert_policy import (  # noqa: E402
    assert_calibration_seeds_resolvable,
    assert_natural_calibration_seeds_cleared,
    assert_paid_pilot_rates_configured,
    compensation_rates_unset,
    load_attribution_policy,
    load_calibration_seeds_policy,
    load_compensation_policy,
    load_qualification_policy,
)

STAFFING_EVIDENCE_PATH = (
    ROOT / "governance" / "evidence" / "natural-adjudication-staffing.json"
)


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: int
    name: str
    passed: bool
    blocking: bool
    detail: str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StaffingDomain(StrictModel):
    domain_profile: str = Field(min_length=1)
    independent_adjudicator_ids: list[str] = Field(default_factory=list)


class NaturalAdjudicationStaffingRoster(StrictModel):
    """Evidence artifact for gate 7 (two-domain natural holdout staffing)."""

    roster_version: str = "0.1"
    status: Literal["blocked", "pending", "ready"]
    blocked_reason: str | None = None
    performance_claims_authorized: bool = False
    minimum_domains_required: int = Field(default=2, ge=2)
    min_independent_adjudicators_per_domain: int = Field(default=2, ge=1)
    domains: list[StaffingDomain] = Field(default_factory=list)
    notes: str = ""

    @field_validator("performance_claims_authorized")
    @classmethod
    def claims_locked(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return value

    @model_validator(mode="after")
    def ready_requires_staffing(self) -> NaturalAdjudicationStaffingRoster:
        if self.status == "ready":
            if self.blocked_reason:
                raise ValueError("ready staffing roster must not set blocked_reason")
            staffed = [
                domain
                for domain in self.domains
                if len(set(domain.independent_adjudicator_ids))
                >= self.min_independent_adjudicators_per_domain
            ]
            if len(staffed) < self.minimum_domains_required:
                raise ValueError(
                    "ready staffing roster requires "
                    f">={self.minimum_domains_required} domains with "
                    f">={self.min_independent_adjudicators_per_domain} "
                    "independent adjudicators each"
                )
        elif self.status == "blocked" and not (self.blocked_reason or "").strip():
            raise ValueError("blocked staffing roster requires blocked_reason")
        return self


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _gate_production(adapter: str, root: Path, gate_id: int, name: str) -> GateResult:
    evidence = _relative(root / "MANIFEST.json")
    min_count = ADAPTER_READY_MINIMA.get(adapter, 10)
    try:
        section = production_section_for(adapter, root)
        manifest = load_production_manifest(root / "MANIFEST.json")
    except Exception as exc:  # noqa: BLE001
        return GateResult(
            gate_id,
            name,
            False,
            True,
            f"evidence={evidence} error: {exc}",
        )
    ready = (
        section.status == ProductionIntakeStatus.READY
        and section.export_count >= min_count
        and manifest.performance_claims_authorized is False
    )
    detail = (
        f"evidence={evidence} status={section.status.value} "
        f"exports={section.export_count} (minimum {min_count})"
    )
    if section.blocked_reason:
        detail = f"{detail}; blocked_reason={section.blocked_reason}"
    return GateResult(gate_id, name, ready, True, detail)


def _load_staffing_roster(path: Path) -> tuple[NaturalAdjudicationStaffingRoster | None, str]:
    if not path.is_file():
        return None, f"evidence missing: {_relative(path)}"
    try:
        roster = NaturalAdjudicationStaffingRoster.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"evidence={_relative(path)} invalid: {exc}"
    return roster, f"evidence={_relative(path)}"


def _gate_staffing(gate_id: int) -> GateResult:
    roster, detail_prefix = _load_staffing_roster(STAFFING_EVIDENCE_PATH)
    if roster is None:
        return GateResult(
            gate_id,
            "two_domain_natural_adjudication_staffing",
            False,
            True,
            detail_prefix,
        )
    staffed = [
        domain.domain_profile
        for domain in roster.domains
        if len(set(domain.independent_adjudicator_ids))
        >= roster.min_independent_adjudicators_per_domain
    ]
    passed = (
        roster.status == "ready"
        and len(staffed) >= roster.minimum_domains_required
        and roster.performance_claims_authorized is False
    )
    detail = (
        f"{detail_prefix} status={roster.status} "
        f"staffed_domains={len(staffed)}/{roster.minimum_domains_required}"
    )
    if roster.blocked_reason:
        detail = f"{detail}; blocked_reason={roster.blocked_reason}"
    return GateResult(
        gate_id,
        "two_domain_natural_adjudication_staffing",
        passed,
        True,
        detail,
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
            f"evidence={_relative(trust)}; production public keys present; "
            "private keys must stay offline",
        )
    )

    try:
        load_qualification_policy()
        compensation = load_compensation_policy()
        load_attribution_policy()
        seeds = load_calibration_seeds_policy()
        assert_calibration_seeds_resolvable(seeds)
        unset = compensation_rates_unset(compensation)
        natural_slots = seeds.natural_seed_slots
        expert_ok = True
        expert_detail = (
            "policy objects load; calibration seeds resolve; "
            f"paid_pilot_rates={'set' if not unset else 'unset->blocked'}; "
            f"natural_seed_slots={natural_slots.status}"
        )
        if unset:
            try:
                assert_paid_pilot_rates_configured(compensation)
            except Exception:  # noqa: BLE001
                pass  # informational: rates unset is expected until funded
        try:
            assert_natural_calibration_seeds_cleared(seeds)
            expert_detail += "; natural seeds cleared"
        except Exception as natural_exc:  # noqa: BLE001
            expert_detail += f"; natural seeds blocked ({natural_exc})"
    except Exception as exc:  # noqa: BLE001
        expert_ok = False
        expert_detail = str(exc)
    results.append(
        GateResult(5, "expert_ops_policy_objects", expert_ok, False, expert_detail)
    )

    natural_count, natural_detail = discover_natural_decision_count(ROOT)
    denominators = measure_current_denominators(
        natural_decision_count=natural_count,
        repo_root=ROOT,
    )
    sessions = _relative(natural_session_manifest_dir(ROOT))
    results.append(
        GateResult(
            6,
            "matcher_audit_natural_volume",
            denominators.natural_dod_met,
            True,
            (
                f"{natural_detail}; "
                f"natural={denominators.natural_decisions_available} "
                f"sample_fixture_reviews={denominators.sample_decisions_available} "
                f"dod_met={denominators.natural_dod_met}; "
                f"sessions_dir={sessions}"
            ),
        )
    )

    results.append(_gate_staffing(7))

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
        STAFFING_EVIDENCE_PATH,
    ):
        if path.is_file():
            payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("performance_claims_authorized") is True:
                claims_locked = False
    results.append(
        GateResult(
            9,
            "performance_claims_locked",
            claims_locked,
            True,
            "performance_claims_authorized must remain false (section 12 stays locked)",
        )
    )

    results.append(
        GateResult(
            10,
            "v09_checklist_document",
            (ROOT / "docs" / "v0.9-beta-go-no-go.md").is_file(),
            False,
            "checklist document present; GO only when this script exits 0",
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
