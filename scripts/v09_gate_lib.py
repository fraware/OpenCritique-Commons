#!/usr/bin/env python3
"""Shared primitives for v0.9 engineering and scientific gate evaluators.

Scientific blocking gates (PR 42 / PR 43) require cryptographically verified
``SignedEvidenceEnvelope`` artifacts under ``governance/evidence/attestations/``.
Boolean JSON, roster status flags, ledger counts, and MANIFEST presence alone
do **not** flip a scientific gate to PASS. Holdout gate #7 requires an attested
holdout set of >=40 natural cases (not ledger ``IMPORTED`` count alone).
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

from opencritique_acquisition.models import (  # noqa: E402
    AcquisitionStatus,
    load_ledger,
)
from opencritique_adapters.production_fixtures import (  # noqa: E402
    ADAPTER_READY_MINIMA,
    COARSE_PRODUCTION,
    OPENREVIEWER_PRODUCTION,
    load_production_manifest,
    production_section_for,
)
from opencritique_evaluation.attestations import (  # noqa: E402
    EvidenceAttestationKind,
)
from opencritique_evaluation.evidence_verify import (  # noqa: E402
    EvidenceVerificationReport,
    load_evidence_envelope,
    missing_attestation_report,
    verify_evidence_envelope,
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
from opencritique_evaluation.trust import (  # noqa: E402
    TrustPolicyMode,
    VerificationFailureReason,
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
ATTESTATIONS_DIR = ROOT / "governance" / "evidence" / "attestations"
DEFAULT_EVIDENCE_TRUST_STORE = ROOT / "trust" / "scorecard-trust-store.json"
SAMPLE_SOURCE_IDS = frozenset({"maintainer-owned-sample-corpus"})
NATURAL_HOLDOUT_MINIMUM = 40

ATTESTATION_ENVELOPE_PATHS: dict[EvidenceAttestationKind, Path] = {
    EvidenceAttestationKind.NATURAL_CORPUS: (
        ATTESTATIONS_DIR / "natural-corpus.envelope.json"
    ),
    EvidenceAttestationKind.EXPERT_STAFFING: (
        ATTESTATIONS_DIR / "expert-staffing.envelope.json"
    ),
    EvidenceAttestationKind.MATCHER_AUDIT_COMPLETION: (
        ATTESTATIONS_DIR / "matcher-audit-completion.envelope.json"
    ),
    EvidenceAttestationKind.HOLDOUT_CUSTODY: (
        ATTESTATIONS_DIR / "holdout-custody.envelope.json"
    ),
    EvidenceAttestationKind.INDEPENDENT_EVALUATION: (
        ATTESTATIONS_DIR / "independent-evaluation.envelope.json"
    ),
}


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: int
    name: str
    passed: bool
    blocking: bool
    detail: str
    verification_report: dict[str, Any] | None = None


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


def reviewer_export_envelope_path(adapter: str) -> Path:
    return ATTESTATIONS_DIR / f"reviewer-export-{adapter}.envelope.json"


def _report_dict(report: EvidenceVerificationReport) -> dict[str, Any]:
    return report.model_dump(mode="json")


def _verify_attestation_file(
    path: Path,
    *,
    kind: EvidenceAttestationKind,
    subject_binding_check: dict[str, Any] | None = None,
    expected_bindings: dict[str, str] | None = None,
    trust_store_path: Path = DEFAULT_EVIDENCE_TRUST_STORE,
    policy_mode: TrustPolicyMode = TrustPolicyMode.PRODUCTION,
) -> EvidenceVerificationReport:
    rel = relative(path)
    if not path.is_file():
        return missing_attestation_report(
            expected_path=rel,
            attestation_kind=kind,
            policy_mode=policy_mode,
        )
    try:
        envelope = load_evidence_envelope(path)
    except Exception as exc:  # noqa: BLE001
        return EvidenceVerificationReport(
            ok=False,
            reason=VerificationFailureReason.MISSING_ATTESTATION,
            detail=f"missing_attestation: envelope at {rel} failed to parse: {exc}",
            artifact_path=rel,
            signature_status="invalid",
            attestation_kind=kind,
            policy_mode=policy_mode,
        )
    return verify_evidence_envelope(
        envelope,
        expected_kind=kind,
        trust_store_path=trust_store_path if trust_store_path.is_file() else None,
        policy_mode=policy_mode,
        artifact_path=rel,
        expected_bindings=expected_bindings,
        subject_binding_check=subject_binding_check,
    )


def _gate_from_attestation(
    gate_id: int,
    name: str,
    report: EvidenceVerificationReport,
    *,
    blocking: bool = True,
    extra_detail: str = "",
) -> GateResult:
    reason = report.reason.value if report.reason else ("ok" if report.ok else "failed")
    detail = (
        f"attestation={report.artifact_path or 'missing'} "
        f"signature_status={report.signature_status} "
        f"reason={reason} "
        f"authority={report.authority_id or '-'} "
        f"revocation={report.revocation_status} "
        f"binding_ok={report.binding_ok}"
    )
    if report.detail:
        detail = f"{detail}; {report.detail}"
    if extra_detail:
        detail = f"{detail}; {extra_detail}"
    return GateResult(
        gate_id,
        name,
        report.ok,
        blocking,
        detail,
        verification_report=_report_dict(report),
    )


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


def count_natural_rights_cleared_cases() -> tuple[int, str, list[str]]:
    """Count non-sample imported cases with evaluation-use authorization."""
    if not ACQUISITION_LEDGER_PATH.is_file():
        return 0, f"evidence missing: {relative(ACQUISITION_LEDGER_PATH)}", []
    try:
        ledger = load_ledger(ACQUISITION_LEDGER_PATH)
    except Exception as exc:  # noqa: BLE001
        return 0, f"evidence={relative(ACQUISITION_LEDGER_PATH)} invalid: {exc}", []
    natural = [
        source
        for source in ledger.sources
        if source.status == AcquisitionStatus.IMPORTED
        and source.source_id not in SAMPLE_SOURCE_IDS
        and source.evaluation_use_authorized
    ]
    case_ids: list[str] = []
    for source in natural:
        # Ledger sources may expose case id lists in later schemas; fall back to
        # synthetic placeholders from counts only when no ids are present.
        source_case_ids = getattr(source, "imported_case_ids", None)
        if isinstance(source_case_ids, list) and source_case_ids:
            case_ids.extend(str(item) for item in source_case_ids)
        else:
            case_ids.extend(
                f"{source.source_id}:case:{i}"
                for i in range(source.imported_case_count)
            )
    count = sum(source.imported_case_count for source in natural)
    detail = (
        f"evidence={relative(ACQUISITION_LEDGER_PATH)} "
        f"natural_rights_cleared_cases={count} "
        f"(sample sources excluded)"
    )
    return count, detail, case_ids


def gate_natural_rights_cleared(gate_id: int, *, blocking: bool = True) -> GateResult:
    count, ledger_detail, case_ids = count_natural_rights_cleared_cases()
    path = ATTESTATION_ENVELOPE_PATHS[EvidenceAttestationKind.NATURAL_CORPUS]
    report = _verify_attestation_file(
        path,
        kind=EvidenceAttestationKind.NATURAL_CORPUS,
        subject_binding_check={
            "natural_case_ids": case_ids,
            "natural_case_count": count,
        }
        if count > 0
        else None,
    )
    return _gate_from_attestation(
        gate_id,
        "natural_rights_cleared_cases",
        report,
        blocking=blocking,
        extra_detail=ledger_detail,
    )


def gate_production(adapter: str, root: Path, gate_id: int, name: str) -> GateResult:
    evidence = relative(root / "MANIFEST.json")
    min_count = ADAPTER_READY_MINIMA.get(adapter, 10)
    artifact_hashes: list[str] = []
    export_count = 0
    section_detail = ""
    try:
        section = production_section_for(adapter, root)
        manifest = load_production_manifest(root / "MANIFEST.json")
        export_count = section.export_count
        artifact_hashes = [item.content_sha256 for item in manifest.artifacts]
        section_detail = (
            f"evidence={evidence} status={section.status.value} "
            f"exports={export_count} (minimum {min_count})"
        )
        if section.blocked_reason:
            section_detail = f"{section_detail}; blocked_reason={section.blocked_reason}"
    except Exception as exc:  # noqa: BLE001
        section_detail = f"evidence={evidence} error: {exc}"

    path = reviewer_export_envelope_path(adapter)
    binding = None
    if artifact_hashes:
        binding = {
            "adapter": adapter,
            "artifact_content_hashes": artifact_hashes,
            "export_count": export_count,
        }
    report = _verify_attestation_file(
        path,
        kind=EvidenceAttestationKind.REVIEWER_EXPORT_AUTHENTICITY,
        subject_binding_check=binding,
    )
    return _gate_from_attestation(
        gate_id,
        name,
        report,
        blocking=True,
        extra_detail=section_detail,
    )


def gate_staffing(gate_id: int, *, blocking: bool = True) -> GateResult:
    roster, detail_prefix = load_staffing_roster(STAFFING_EVIDENCE_PATH)
    binding = None
    roster_detail = detail_prefix
    if roster is not None:
        staffed = [
            domain.domain_profile
            for domain in roster.domains
            if len(set(domain.independent_adjudicator_ids))
            >= roster.min_independent_adjudicators_per_domain
        ]
        adjudicator_ids = [
            adj_id
            for domain in roster.domains
            for adj_id in domain.independent_adjudicator_ids
        ]
        roster_detail = (
            f"{detail_prefix} status={roster.status} "
            f"staffed_domains={len(staffed)}/{roster.minimum_domains_required}"
        )
        if roster.blocked_reason:
            roster_detail = f"{roster_detail}; blocked_reason={roster.blocked_reason}"
        if adjudicator_ids:
            binding = {
                "independent_adjudicator_ids": adjudicator_ids,
                "domain_profiles": [d.domain_profile for d in roster.domains],
            }

    path = ATTESTATION_ENVELOPE_PATHS[EvidenceAttestationKind.EXPERT_STAFFING]
    report = _verify_attestation_file(
        path,
        kind=EvidenceAttestationKind.EXPERT_STAFFING,
        subject_binding_check=binding,
    )
    return _gate_from_attestation(
        gate_id,
        "qualified_expert_staffing",
        report,
        blocking=blocking,
        extra_detail=roster_detail,
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
        "private keys must stay offline; evidence_authority attestations "
        "verified separately per scientific gate",
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
    volume_detail = (
        f"{natural_detail}; "
        f"natural={denominators.natural_decisions_available} "
        f"sample_fixture_reviews={denominators.sample_decisions_available} "
        f"dod_met={denominators.natural_dod_met}; "
        f"sessions_dir={sessions} "
        f"(sampled_count alone is not attestation)"
    )
    path = ATTESTATION_ENVELOPE_PATHS[
        EvidenceAttestationKind.MATCHER_AUDIT_COMPLETION
    ]
    report = _verify_attestation_file(
        path,
        kind=EvidenceAttestationKind.MATCHER_AUDIT_COMPLETION,
    )
    return _gate_from_attestation(
        gate_id,
        "matcher_audit_natural_volume",
        report,
        blocking=blocking,
        extra_detail=volume_detail,
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
        "engineering docs present; attested natural holdout custody missing",
    )


def gate_holdout_custody_scientific(
    gate_id: int, *, blocking: bool = True
) -> GateResult:
    """Scientific: verified holdout custody over attested set (≥40 cases).

    Pass requires a cryptographically verified ``HoldoutCustodyAttestation``
    bound to a holdout manifest hash + access-log head hash, freeze time, and
    ``natural_case_count`` ≥ ``NATURAL_HOLDOUT_MINIMUM`` **inside the attested
    holdout set**. Ledger ``IMPORTED`` counts and protocol markdown alone do
    not unlock this gate.
    """
    protocol = ROOT / "docs" / "matcher-audit-protocol.md"
    protocol_ok = protocol.is_file()
    ledger_count, ledger_detail, _case_ids = count_natural_rights_cleared_cases()
    path = ATTESTATION_ENVELOPE_PATHS[EvidenceAttestationKind.HOLDOUT_CUSTODY]
    report = _verify_attestation_file(
        path,
        kind=EvidenceAttestationKind.HOLDOUT_CUSTODY,
        subject_binding_check={
            "require_minimum_natural_cases": NATURAL_HOLDOUT_MINIMUM,
            "require_custody_fields": True,
        },
    )
    extra = (
        f"{ledger_detail} (informational only; not the gate denominator); "
        f"protocol={relative(protocol)} present={protocol_ok}; "
        f"attested_holdout_minimum={NATURAL_HOLDOUT_MINIMUM}; "
        f"ledger_natural_imports={ledger_count}"
    )
    return _gate_from_attestation(
        gate_id,
        "holdout_custody",
        report,
        blocking=blocking,
        extra_detail=extra,
    )


def gate_independent_evaluation(gate_id: int, *, blocking: bool = True) -> GateResult:
    """Scientific: verified independent-evaluation attestation."""
    benchmarks_root = ROOT / "benchmarks"
    independent: list[str] = []
    benchmark_ids: list[str] = []
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
                benchmark_ids.append(manifest.benchmark_id)
    scan_detail = (
        f"expert_natural_independent_benchmarks={len(independent)} "
        f"scan_errors={scan_errors}"
    )
    if independent:
        scan_detail = f"{scan_detail}; evidence={independent[0]}"
    else:
        scan_detail = (
            f"{scan_detail}; no expert_natural benchmark with "
            "independent_evaluation=true"
        )

    path = ATTESTATION_ENVELOPE_PATHS[
        EvidenceAttestationKind.INDEPENDENT_EVALUATION
    ]
    binding = None
    if benchmark_ids:
        binding = {
            "benchmark_ids": benchmark_ids,
            "require_independent": True,
        }
    report = _verify_attestation_file(
        path,
        kind=EvidenceAttestationKind.INDEPENDENT_EVALUATION,
        subject_binding_check=binding,
    )
    return _gate_from_attestation(
        gate_id,
        "independent_evaluation",
        report,
        blocking=blocking,
        extra_detail=scan_detail,
    )


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
        if item.verification_report:
            vr = item.verification_report
            print(
                "    verification_report: "
                f"path={vr.get('artifact_path')} "
                f"content_hash={vr.get('content_hash')} "
                f"signature_status={vr.get('signature_status')} "
                f"authority={vr.get('authority_id')} "
                f"bindings={vr.get('bindings')} "
                f"reason={vr.get('reason')} "
                f"revocation={vr.get('revocation_status')}"
            )
    if blocking_failures:
        print(no_go_message.format(count=len(blocking_failures)))
        return 1
    print(go_message)
    return 0


__all__ = [
    "ATTESTATIONS_DIR",
    "ATTESTATION_ENVELOPE_PATHS",
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
    "reviewer_export_envelope_path",
]
