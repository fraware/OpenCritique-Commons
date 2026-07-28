from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db_models import UseGrantORM
from .schemas import DataUse, GrantStatus
from .timeutils import as_utc


def active_grant(
    session: Session,
    *,
    case_id: str,
    case_version: str,
    use: DataUse,
) -> UseGrantORM | None:
    now = datetime.now(timezone.utc)
    rows = session.scalars(
        select(UseGrantORM)
        .where(
            UseGrantORM.case_id == case_id,
            UseGrantORM.case_version == case_version,
            UseGrantORM.use_type == use.value,
            UseGrantORM.status == GrantStatus.ACTIVE.value,
        )
        .order_by(UseGrantORM.created_at.desc())
    ).all()
    for row in rows:
        if row.expires_at is None or as_utc(row.expires_at) > now:
            return row
    return None


def require_use_grant(
    session: Session,
    *,
    case_id: str,
    case_version: str,
    use: DataUse,
) -> UseGrantORM:
    grant = active_grant(
        session,
        case_id=case_id,
        case_version=case_version,
        use=use,
    )
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"case lacks an active {use.value} authorization",
        )
    return grant
