from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


WorkplaceType = Literal["remote", "hybrid", "onsite", "unknown"]
JobStatus = Literal["active", "stale", "closed", "unknown"]
SourceType = Literal["ats", "aggregator", "company_page", "enrichment", "other"]


class SearchQuery(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    workplace_types: list[WorkplaceType] = Field(default_factory=list)
    seniority: list[str] = Field(default_factory=list)

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("At least one keyword is required")
        return cleaned


class CompanyRecord(BaseModel):
    normalized_name: str
    display_name: str
    careers_url: HttpUrl | None = None
    headquarters: str | None = None
    company_type: str | None = None
    notes: str | None = None

    @field_validator("normalized_name", "display_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Company names cannot be empty")
        return cleaned


class RawJobPosting(BaseModel):
    source: str
    source_type: SourceType = "ats"
    source_job_id: str
    source_url: HttpUrl
    title: str
    company_name: str
    location_text: str | None = None
    workplace_type: WorkplaceType = "unknown"
    posted_at: datetime | None = None
    description_snippet: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    raw_tags: list[str] = Field(default_factory=list)

    @field_validator("source", "source_job_id", "title", "company_name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_salary_range(self) -> "RawJobPosting":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min cannot be greater than salary_max")
        return self


class NormalizedJobPosting(BaseModel):
    source: str
    source_job_id: str
    source_url: HttpUrl
    canonical_key: str
    title: str
    company: CompanyRecord
    location_text: str | None = None
    workplace_type: WorkplaceType = "unknown"
    posted_at: datetime | None = None
    description_snippet: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    raw_tags: list[str] = Field(default_factory=list)
    status: JobStatus = "unknown"

    @field_validator("canonical_key", "title", "source", "source_job_id")
    @classmethod
    def validate_required_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_salary_range(self) -> "NormalizedJobPosting":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min cannot be greater than salary_max")
        return self


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
