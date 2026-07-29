"""Adjudication assignment guards (issue #14)."""

from __future__ import annotations

from dataclasses import dataclass


class AssignmentGuardError(ValueError):
    code: str = "assignment_guard_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


@dataclass(frozen=True, slots=True)
class AssignmentRecord:
    task_id: str
    concern_id: str
    slot: str
    assigned_to: str | None
    status: str


def blocks_duplicate_primary(
    *,
    candidate: AssignmentRecord,
    existing: list[AssignmentRecord],
    adjudicator_id: str,
) -> bool:
    """Return True when claiming candidate would duplicate primary/secondary for one concern."""
    if candidate.assigned_to is not None and candidate.status in {"claimed", "completed"}:
        return True
    for item in existing:
        if item.task_id == candidate.task_id:
            continue
        if item.concern_id != candidate.concern_id:
            continue
        if item.assigned_to != adjudicator_id:
            continue
        if item.status not in {"claimed", "completed"}:
            continue
        return True
    return False


def assert_no_duplicate_primary(
    *,
    candidate: AssignmentRecord,
    existing: list[AssignmentRecord],
    adjudicator_id: str,
) -> None:
    if blocks_duplicate_primary(
        candidate=candidate,
        existing=existing,
        adjudicator_id=adjudicator_id,
    ):
        raise AssignmentGuardError(
            f"adjudicator {adjudicator_id} already holds a primary/secondary assignment "
            f"for concern {candidate.concern_id}",
            code="duplicate_primary",
        )
