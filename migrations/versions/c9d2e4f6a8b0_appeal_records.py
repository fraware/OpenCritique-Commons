"""appeal_records

Add append-only appeal/correction records for determinations.

Revision ID: c9d2e4f6a8b0
Revises: b2c4d6e8f0a1
Create Date: 2026-07-29 01:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d2e4f6a8b0"
down_revision: Union[str, Sequence[str], None] = "b2c4d6e8f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appeal_records",
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=255), nullable=False),
        sa.Column("case_version", sa.String(length=64), nullable=False),
        sa.Column("concern_id", sa.String(length=255), nullable=False),
        sa.Column("determination_id", sa.String(length=64), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("predecessor_record_id", sa.String(length=64), nullable=True),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("record_id"),
    )
    with op.batch_alter_table("appeal_records", schema=None) as batch_op:
        batch_op.create_index(
            "ix_appeal_concern_created", ["concern_id", "created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("appeal_records", schema=None) as batch_op:
        batch_op.drop_index("ix_appeal_concern_created")
    op.drop_table("appeal_records")
