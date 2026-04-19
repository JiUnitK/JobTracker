"""add job scoring fields

Revision ID: 20260419_0002
Revises: 20260418_0001
Create Date: 2026-04-19 09:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_0002"
down_revision = "20260418_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("fit_score", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("hiring_score", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("priority_score", sa.Integer(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("score_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("jobs", "score_payload")
    op.drop_column("jobs", "priority_score")
    op.drop_column("jobs", "hiring_score")
    op.drop_column("jobs", "fit_score")
