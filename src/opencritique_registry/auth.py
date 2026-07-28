from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db_models import ApiTokenORM, PrincipalORM
from .ids import new_id
from .schemas import PrincipalRole, TokenIssued
from .timeutils import as_utc


@dataclass(frozen=True)
class PrincipalContext:
    actor_id: str
    role: PrincipalRole
    display_name: str | None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(
    session: Session,
    *,
    actor_id: str,
    expires_at: datetime | None = None,
) -> TokenIssued:
    principal = session.get(PrincipalORM, actor_id)
    if principal is None or not principal.active:
        raise ValueError("principal does not exist or is inactive")
    secret = secrets.token_urlsafe(32)
    token_id = new_id("octok")
    token = f"{token_id}.{secret}"
    session.add(
        ApiTokenORM(
            token_id=token_id,
            actor_id=actor_id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
    )
    session.flush()
    return TokenIssued(token_id=token_id, token=token, actor_id=actor_id, expires_at=expires_at)



def revoke_token(session: Session, token_id: str) -> datetime:
    row = session.get(ApiTokenORM, token_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="token not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        session.flush()
    return row.revoked_at

def authenticate_token(session: Session, token: str) -> PrincipalContext:
    token_row = session.scalar(
        select(ApiTokenORM).where(ApiTokenORM.token_hash == hash_token(token))
    )
    now = datetime.now(timezone.utc)
    if token_row is None or token_row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    if token_row.expires_at is not None and as_utc(token_row.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="expired token")
    principal = session.get(PrincipalORM, token_row.actor_id)
    if principal is None or not principal.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="inactive principal")
    return PrincipalContext(
        actor_id=principal.actor_id,
        role=PrincipalRole(principal.role),
        display_name=principal.display_name,
    )


def get_session(request: Request):
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def current_principal(
    request: Request,
    session: Session = Depends(get_session),
) -> PrincipalContext:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="bearer token required"
        )
    return authenticate_token(session, token)


def require_roles(*roles: PrincipalRole):
    allowed = set(roles)

    def dependency(principal: PrincipalContext = Depends(current_principal)) -> PrincipalContext:
        if principal.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")
        return principal

    return dependency
