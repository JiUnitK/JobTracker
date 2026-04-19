"""initial schema

Revision ID: 20260418_0001
Revises:
Create Date: 2026-04-18 18:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260418_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("careers_url", sa.String(length=1024), nullable=True),
        sa.Column("headquarters", sa.String(length=255), nullable=True),
        sa.Column("company_type", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_companies_normalized_name", "companies", ["normalized_name"], unique=True)

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reliability_tier", sa.String(length=16), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sources_name", "sources", ["name"], unique=True)

    op.create_table(
        "search_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("canonical_key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("workplace_type", sa.String(length=32), nullable=False),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column("seniority", sa.String(length=64), nullable=True),
        sa.Column("description_snippet", sa.Text(), nullable=True),
        sa.Column("salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_currency", sa.String(length=8), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_status", sa.String(length=32), nullable=False),
        sa.Column("best_source_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.UniqueConstraint("canonical_key", name="uq_jobs_canonical_key"),
    )
    op.create_index("ix_jobs_canonical_key", "jobs", ["canonical_key"], unique=False)
    op.create_index("ix_jobs_company_id", "jobs", ["company_id"], unique=False)
    op.create_index("ix_jobs_title", "jobs", ["title"], unique=False)

    op.create_table(
        "job_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("search_run_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_job_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("observed_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["search_run_id"], ["search_runs.id"]),
        sa.UniqueConstraint(
            "job_id",
            "search_run_id",
            "source",
            "source_job_id",
            name="uq_job_observations_source_per_run",
        ),
    )
    op.create_index("ix_job_observations_job_id", "job_observations", ["job_id"], unique=False)
    op.create_index(
        "ix_job_observations_search_run_id", "job_observations", ["search_run_id"], unique=False
    )
    op.create_index("ix_job_observations_source", "job_observations", ["source"], unique=False)
    op.create_index(
        "ix_job_observations_source_job_id",
        "job_observations",
        ["source_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_observations_source_job_id", table_name="job_observations")
    op.drop_index("ix_job_observations_source", table_name="job_observations")
    op.drop_index("ix_job_observations_search_run_id", table_name="job_observations")
    op.drop_index("ix_job_observations_job_id", table_name="job_observations")
    op.drop_table("job_observations")

    op.drop_index("ix_jobs_title", table_name="jobs")
    op.drop_index("ix_jobs_company_id", table_name="jobs")
    op.drop_index("ix_jobs_canonical_key", table_name="jobs")
    op.drop_table("jobs")

    op.drop_table("search_runs")

    op.drop_index("ix_sources_name", table_name="sources")
    op.drop_table("sources")

    op.drop_index("ix_companies_normalized_name", table_name="companies")
    op.drop_table("companies")
