"""Expert policy objects and assignment guards (issue #14)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from opencritique_registry.assignment_guards import (
    AssignmentGuardError,
    AssignmentRecord,
    assert_no_duplicate_primary,
    blocks_duplicate_primary,
)
from opencritique_registry.expert_policy import (
    ExpertPolicyError,
    assert_calibration_seeds_resolvable,
    is_qualification_expired,
    load_attribution_policy,
    load_calibration_seeds_policy,
    load_compensation_policy,
    load_qualification_policy,
    qualification_expiry_at,
    require_conflict_disclosure,
)

ROOT = Path(__file__).resolve().parents[1]


def test_qualification_policy_loads_and_expiry() -> None:
    policy = load_qualification_policy()
    assert policy.performance_claims_authorized is False
    threshold = policy.threshold_for("empirical_ml")
    assert threshold.expiry_days == 180
    start = datetime(2026, 1, 1, tzinfo=UTC)
    expires = qualification_expiry_at(
        valid_from=start, domain_profile="empirical_ml", policy=policy
    )
    assert expires == start + timedelta(days=180)
    assert is_qualification_expired(expires_at=expires, now=expires) is True
    assert is_qualification_expired(
        expires_at=expires, now=expires - timedelta(seconds=1)
    ) is False


def test_compensation_and_attribution_policies() -> None:
    compensation = load_compensation_policy()
    assert compensation.payment_secrets_prohibited is True
    assert compensation.performance_claims_authorized is False
    assert all(slot.amount_minor is None for slot in compensation.schedule)
    attribution = load_attribution_policy()
    assert attribution.opt_in_required is True
    assert attribution.conflict_disclosure_required is True
    assert attribution.default_public_attribution is False


def test_calibration_seeds_resolvable() -> None:
    policy = load_calibration_seeds_policy()
    assert policy.source_class == "maintainer_owned_sample_corpus"
    seeds = assert_calibration_seeds_resolvable(policy, repo_root=ROOT)
    assert len(seeds) >= 3


def test_conflict_disclosure_required() -> None:
    require_conflict_disclosure("none")
    require_conflict_disclosure("disclosed", "co-author on cited paper")
    with pytest.raises(ExpertPolicyError) as missing:
        require_conflict_disclosure("disclosed", "  ")
    assert missing.value.code == "conflict_description_required"
    with pytest.raises(ExpertPolicyError) as disq:
        require_conflict_disclosure("disqualifying", "employer")
    assert disq.value.code == "conflict_disqualifying"


def test_duplicate_primary_assignment_prevention() -> None:
    candidate = AssignmentRecord(
        task_id="t2",
        concern_id="c1",
        slot="secondary",
        assigned_to=None,
        status="pending",
    )
    existing = [
        AssignmentRecord(
            task_id="t1",
            concern_id="c1",
            slot="primary",
            assigned_to="expert-a",
            status="claimed",
        )
    ]
    assert blocks_duplicate_primary(
        candidate=candidate, existing=existing, adjudicator_id="expert-a"
    )
    with pytest.raises(AssignmentGuardError) as exc:
        assert_no_duplicate_primary(
            candidate=candidate, existing=existing, adjudicator_id="expert-a"
        )
    assert exc.value.code == "duplicate_primary"
    assert not blocks_duplicate_primary(
        candidate=candidate, existing=existing, adjudicator_id="expert-b"
    )


def test_expert_ops_doc_lists_runtime_loaders() -> None:
    text = (ROOT / "docs" / "expert-program-ops.md").read_text(encoding="utf-8")
    assert "load_qualification_policy" in text
    assert "assignment_guards" in text
