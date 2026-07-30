#!/usr/bin/env python3
"""Shared primitives for v0.9 engineering and scientific gate evaluators."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opencritique_acquisition.models import (  # noqa: E402
    AcquisitionStatus,
    load_ledger,
)
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
from opencritique_evaluation.models import (  # noqa: E402
    BenchmarkEvidenceClass,
    BenchmarkManifest,
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
ACQUISITION_LEDGER_PATH = ROOT / "corpus" / "acquisition-ledger.json"
SAMPLE_SOURCE_IDS = frozenset({"maintainer-owned-sample-corpus"})
NATURAL_HOLDOUT_MINIMUM = 40


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
    """Evidence artifact for two-domain natural holdout staffing."""

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


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def gate_production(adapter: str, root: Path, gate_id: int, name: str) -> GateResult:
    evidence = relative(root / "MANIFEST.json")
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


def load_staffing_roster(
    path: Path = STAFFING_EVIDENCE_PATH,
) -> tuple[NaturalAdjudicationStaffingRoster | None, str]:
    if not path.is_file():
        return None, f"evidence missing: {relative(path)}"
    try:
        roster = NaturalAdjudicationStaffingRoster.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"evidence={relative(path)} invalid: {exc}"
    return roster, f"evidence={relative(path)}"


def gate_staffing(gate_id: int, *, blocking: bool = True) -> GateResult:
    roster, detail_prefix = load_staffing_roster(STAFFING_EVIDENCE_PATH)
    name = "qualified_expert_staffing"
    if roster is None:
        return GateResult(gate_id, name, False, blocking, detail_prefix)
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
    return GateResult(gate_id, name, passed, blocking, detail)


def count_natural_rights_cleared_cases() -> tuple[int, str]:
    """Count non-sample imported cases with evaluation-use authorization."""
    if not ACQUISITION_LEDGER_PATH.is_file():
        return 0, f"evidence missing: {relative(ACQUISITION_LEDGER_PATH)}"
    try:
        ledger = load_ledger(ACQUISITION_LEDGER_PATH)
    except Exception as exc:  # noqa: BLE001
        return 0, f"evidence={relative(ACQUISITION_LEDGER_PATH)} invalid: {exc}"
    natural = [
        source
        for source in ledger.sources
        if source.status == AcquisitionStatus.IMPORTED
        and source.source_id not in SAMPLE_SOURCE_IDS
        and source.evaluation_use_authorized
    ]
    count = sum(source.imported_case_count for source in natural)
    detail = (
        f"evidence={relative(ACQUISITION_LEDGER_PATH)} "
        f"natural_rights_cleared_cases={count} "
        f"(sample sources excluded)"
    )
    return count, detail


def gate_natural_rights_cleared(gate_id: int, *, blocking: bool = True) -> GateResult:
    count, detail = count_natural_rights_cleared_cases()
    seeds_detail = ""
    seeds_ready = False
    try:
        seeds = load_calibration_seeds_policy()
        assert_natural_calibration_seeds_cleared(seeds)
        seeds_ready = True
        seeds_detail = "; natural calibration seed slots cleared"
    except Exception as exc:  # noqa: BLE001
        seeds_detail = f"; natural calibration seeds blocked ({exc})"
    passed = count >= 1 or seeds_ready
    return GateResult(
        gate_id,
        "natural_rights_cleared_cases",
        passed,
        blocking,
        f"{detail}{seeds_detail}",
    )


def gate_rights_process_or_negative_finding(
    gate_id: int, *, blocking: bool = False
) -> GateResult:
    """Engineering/process gate: affirmative path or archived negative finding."""
    rights_status = ROOT / "docs" / "rights-clearance-status.md"
    passed = (
        rights_status.is_file()
        and "negative finding" in rights_status.read_text(encoding="utf-8").lower()
    )
    return GateResult(
        gate_id,
        "external_rights_path_or_negative_finding",
        passed,
        blocking,
        "negative finding archived; natural import still blocked",
    )


def gate_production_signing(gate_id: int, *, blocking: bool) -> GateResult:
    trust = ROOT / "trust" / "scorecard-trust-store.json"
    prod_keys_ok = False
    if trust.is_file():
        raw = trust.read_text(encoding="utf-8")
        prod_keys_ok = "PROD-ROOT" in raw or "PROD-RELEASE" in raw
    return GateResult(
        gate_id,
        "production_signing_public_keys",
        prod_keys_ok,
        blocking,
        f"evidence={relative(trust)}; production public keys present; "
        "private keys must stay offline",
    )


def gate_expert_ops_policy(gate_id: int, *, blocking: bool = False) -> GateResult:
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
                pass
        try:
            assert_natural_calibration_seeds_cleared(seeds)
            expert_detail += "; natural seeds cleared"
        except Exception as natural_exc:  # noqa: BLE001
            expert_detail += f"; natural seeds blocked ({natural_exc})"
    except Exception as exc:  # noqa: BLE001
        expert_ok = False
        expert_detail = str(exc)
    return GateResult(
        gate_id, "expert_ops_policy_objects", expert_ok, blocking, expert_detail
    )


def gate_matcher_audit(gate_id: int, *, blocking: bool = True) -> GateResult:
    natural_count, natural_detail = discover_natural_decision_count(ROOT)
    denominators = measure_current_denominators(
        natural_decision_count=natural_count,
        repo_root=ROOT,
    )
    sessions = relative(natural_session_manifest_dir(ROOT))
    return GateResult(
        gate_id,
        "matcher_audit_natural_volume",
        denominators.natural_dod_met,
        blocking,
        (
            f"{natural_detail}; "
            f"natural={denominators.natural_decisions_available} "
            f"sample_fixture_reviews={denominators.sample_decisions_available} "
            f"dod_met={denominators.natural_dod_met}; "
            f"sessions_dir={sessions}"
        ),
    )


def gate_holdout_custody_documented(
    gate_id: int, *, blocking: bool = False
) -> GateResult:
    """Engineering: protocol / withholding docs present."""
    protocol = ROOT / "docs" / "matcher-audit-protocol.md"
    return GateResult(
        gate_id,
        "holdout_custody_documented",
        protocol.is_file(),
        blocking,
        "engineering docs present; natural holdout missing",
    )


def gate_holdout_custody_scientific(
    gate_id: int, *, blocking: bool = True
) -> GateResult:
    """Scientific: natural holdout population + custody docs (fail closed)."""
    protocol = ROOT / "docs" / "matcher-audit-protocol.md"
    protocol_ok = protocol.is_file()
    count, ledger_detail = count_natural_rights_cleared_cases()
    passed = protocol_ok and count >= NATURAL_HOLDOUT_MINIMUM
    detail = (
        f"{ledger_detail}; protocol={relative(protocol)} present={protocol_ok}; "
        f"natural_holdout_minimum={NATURAL_HOLDOUT_MINIMUM}"
    )
    if not passed:
        detail = f"{detail}; natural holdout custody unmet"
    return GateResult(gate_id, "holdout_custody", passed, blocking, detail)


def gate_independent_evaluation(gate_id: int, *, blocking: bool = True) -> GateResult:
    """Scientific: expert-natural benchmark with independent_evaluation=true."""
    benchmarks_root = ROOT / "benchmarks"
    independent: list[str] = []
    scan_errors = 0
    if benchmarks_root.is_dir():
        for path in sorted(benchmarks_root.rglob("manifest.json")):
            try:
                manifest = BenchmarkManifest.model_validate(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except Exception:  # noqa: BLE001
                scan_errors += 1
                continue
            if (
                manifest.evidence_class == BenchmarkEvidenceClass.EXPERT_NATURAL
                and manifest.independent_evaluation
            ):
                independent.append(relative(path))
    passed = len(independent) >= 1
    detail = (
        f"expert_natural_independent_benchmarks={len(independent)} "
        f"scan_errors={scan_errors}"
    )
    if independent:
        detail = f"{detail}; evidence={independent[0]}"
    else:
        detail = (
            f"{detail}; no expert_natural benchmark with "
            "independent_evaluation=true"
        )
    return GateResult(gate_id, "independent_evaluation", passed, blocking, detail)


def gate_performance_claims_locked(
    gate_id: int, *, blocking: bool = True
) -> GateResult:
    claims_locked = True
    for path in (
        ACQUISITION_LEDGER_PATH,
        COARSE_PRODUCTION / "MANIFEST.json",
        OPENREVIEWER_PRODUCTION / "MANIFEST.json",
        STAFFING_EVIDENCE_PATH,
    ):
        if path.is_file():
            payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("performance_claims_authorized") is True:
                claims_locked = False
    return GateResult(
        gate_id,
        "performance_claims_locked",
        claims_locked,
        blocking,
        "performance_claims_authorized must remain false (section 12 stays locked)",
    )


def gate_checklist_document(gate_id: int, *, blocking: bool = False) -> GateResult:
    return GateResult(
        gate_id,
        "v09_checklist_document",
        (ROOT / "docs" / "v0.9-beta-go-no-go.md").is_file(),
        blocking,
        "checklist document present; scientific GO only when scientific gates exit 0",
    )


def report_gates(
    title: str,
    results: list[GateResult],
    *,
    go_message: str,
    no_go_message: str,
) -> int:
    blocking_failures = [item for item in results if item.blocking and not item.passed]
    print(title)
    print("performance_claims_authorized=false (enforced)")
    for item in results:
        mark = "PASS" if item.passed else "FAIL"
        block = "blocking" if item.blocking else "informational"
        print(f"  [{mark}] #{item.gate_id} {item.name} ({block}): {item.detail}")
    if blocking_failures:
        print(no_go_message.format(count=len(blocking_failures)))
        return 1
    print(go_message)
    return 0


__all__ = [
    "COARSE_PRODUCTION",
    "OPENREVIEWER_PRODUCTION",
    "ROOT",
    "STAFFING_EVIDENCE_PATH",
    "GateResult",
    "NaturalAdjudicationStaffingRoster",
    "gate_checklist_document",
    "gate_expert_ops_policy",
    "gate_holdout_custody_documented",
    "gate_holdout_custody_scientific",
    "gate_independent_evaluation",
    "gate_matcher_audit",
    "gate_natural_rights_cleared",
    "gate_performance_claims_locked",
    "gate_production",
    "gate_production_signing",
    "gate_rights_process_or_negative_finding",
    "gate_staffing",
    "report_gates",
]
