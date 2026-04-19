from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobtracker.storage.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CompanyORM(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    careers_url: Mapped[str | None] = mapped_column(String(1024))
    headquarters: Mapped[str | None] = mapped_column(String(255))
    company_type: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    jobs: Mapped[list["JobORM"]] = relationship(back_populates="company")


class SourceORM(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reliability_tier: Mapped[str] = mapped_column(String(16))
    base_url: Mapped[str | None] = mapped_column(String(1024))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SearchRunORM(Base):
    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="running")
    trigger_type: Mapped[str] = mapped_column(String(32), default="manual")
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)

    observations: Mapped[list["JobObservationORM"]] = relationship(
        back_populates="search_run"
    )


class JobORM(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("canonical_key", name="uq_jobs_canonical_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    canonical_key: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    location_text: Mapped[str | None] = mapped_column(String(255))
    workplace_type: Mapped[str] = mapped_column(String(32), default="unknown")
    employment_type: Mapped[str | None] = mapped_column(String(64))
    seniority: Mapped[str | None] = mapped_column(String(64))
    description_snippet: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[float | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[float | None] = mapped_column(Numeric(12, 2))
    salary_currency: Mapped[str | None] = mapped_column(String(8))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    current_status: Mapped[str] = mapped_column(String(32), default="unknown")
    best_source_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    company: Mapped[CompanyORM] = relationship(back_populates="jobs")
    observations: Mapped[list["JobObservationORM"]] = relationship(
        back_populates="job"
    )


class JobObservationORM(Base):
    __tablename__ = "job_observations"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "search_run_id",
            "source",
            "source_job_id",
            name="uq_job_observations_source_per_run",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    search_run_id: Mapped[int] = mapped_column(ForeignKey("search_runs.id"), index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    source_job_id: Mapped[str] = mapped_column(String(255), index=True)
    source_url: Mapped[str] = mapped_column(String(1024))
    observed_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    parse_status: Mapped[str] = mapped_column(String(32), default="parsed")
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    job: Mapped[JobORM] = relationship(back_populates="observations")
    search_run: Mapped[SearchRunORM] = relationship(back_populates="observations")
