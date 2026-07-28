from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .db_models import AuditEventORM
from .ids import new_id


def record_event(
    session: Session,
    *,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    event_data: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEventORM(
            event_id=new_id("ocaudit"),
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            event_data=event_data or {},
        )
    )
