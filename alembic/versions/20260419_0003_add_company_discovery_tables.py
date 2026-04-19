"""add company discovery tables

Revision ID: 20260419_0003
Revises: 20260419_0002
Create Date: 2026-04-19 16:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_0003"
down_revision = "20260419_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_discoveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("company_url", sa.String(length=1024), nullable=True),
        sa.Column("careers_url", sa.String(length=1024), nullable=True),
        sa.Column("discovery_status", sa.String(length=32), nullable=False),
        sa.Column("resolution_status", sa.String(length=32), nullable=False),
        sa.Column("discovery_score", sa.Integer(), nullable=True),
        sa.Column("fit_score", sa.Integer(), nullable=True),
        sa.Column("hiring_score", sa.Integer(), nullable=True),
        sa.Column("score_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_discoveries_company_id",
        "company_discoveries",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_company_discoveries_normalized_name",
        "company_discoveries",
        ["normalized_name"],
        unique=True,
    )

    op.create_table(
        "company_discovery_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_discovery_id", sa.Integer(), nullable=False),
        sa.Column("search_run_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("company_url", sa.String(length=1024), nullable=True),
        sa.Column("careers_url", sa.String(length=1024), nullable=True),
        sa.Column("job_url", sa.String(length=1024), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("workplace_type", sa.String(length=32), nullable=False),
        sa.Column("evidence_kind", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["company_discovery_id"], ["company_discoveries.id"]),
        sa.ForeignKeyConstraint(["search_run_id"], ["search_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_discovery_observations_company_discovery_id",
        "company_discovery_observations",
        ["company_discovery_id"],
        unique=False,
    )
    op.create_index(
        "ix_company_discovery_observations_search_run_id",
        "company_discovery_observations",
        ["search_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_company_discovery_observations_source_name",
        "company_discovery_observations",
        ["source_name"],
        unique=False,
    )

    op.create_table(
        "company_resolutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_discovery_id", sa.Integer(), nullable=False),
        sa.Column("resolution_type", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 2), nullable=True),
        sa.Column("is_selected", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_discovery_id"], ["company_discoveries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_resolutions_company_discovery_id",
        "company_resolutions",
        ["company_discovery_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_company_resolutions_company_discovery_id", table_name="company_resolutions")
    op.drop_table("company_resolutions")
    op.drop_index(
        "ix_company_discovery_observations_source_name",
        table_name="company_discovery_observations",
    )
    op.drop_index(
        "ix_company_discovery_observations_search_run_id",
        table_name="company_discovery_observations",
    )
    op.drop_index(
        "ix_company_discovery_observations_company_discovery_id",
        table_name="company_discovery_observations",
    )
    op.drop_table("company_discovery_observations")
    op.drop_index("ix_company_discoveries_normalized_name", table_name="company_discoveries")
    op.drop_index("ix_company_discoveries_company_id", table_name="company_discoveries")
    op.drop_table("company_discoveries")
