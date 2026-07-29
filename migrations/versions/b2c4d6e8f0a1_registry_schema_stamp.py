"""registry_schema_stamp

No-op additive revision so previous-release → head migration tests exercise a
real upgrade path after the initial schema revision.

Revision ID: b2c4d6e8f0a1
Revises: e47498e63a9d
Create Date: 2026-07-29 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "b2c4d6e8f0a1"
down_revision: Union[str, Sequence[str], None] = "e47498e63a9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty: advances alembic_version for previous→head path tests.
    # Schema objects remain defined by e47498e63a9d and ORM metadata.
    return


def downgrade() -> None:
    return
