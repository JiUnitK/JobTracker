from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from jobtracker.models import WorkplaceType


AgeConfidence = Literal["high", "medium", "low", "unknown"]
SearchProvider = Literal["brave_search", "other"]
SourceMode = Literal["strict", "broad"]


class InstantJobSearchQuery(BaseModel):
    query: str
    location: str | None = None
    workplace_types: list[WorkplaceType] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Search query cannot be empty")
        return cleaned

    @field_validator("location")
    @classmethod
    def clean_location(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class InstantJobSearchRequest(BaseModel):
    queries: list[InstantJobSearchQuery] = Field(default_factory=list)
    max_age_days: int = 7
    include_unknown_age: bool = False
    use_profile_matching: bool = False
    source_mode: SourceMode = "strict"
    limit: int = 25

    @model_validator(mode="after")
    def validate_request(self) -> "InstantJobSearchRequest":
        if not self.queries:
            raise ValueError("At least one instant job-search query is required")
        if self.max_age_days < 1:
            raise ValueError("max_age_days must be at least 1")
        if self.limit < 1:
            raise ValueError("limit must be at least 1")
        return self


class RawInstantSearchResult(BaseModel):
    provider: SearchProvider = "brave_search"
    source_id: str
    title: str
    url: HttpUrl
    snippet: str | None = None
    published_at: datetime | None = None
    age_text: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_id", "title")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be empty")
        return cleaned

    @field_validator("snippet", "age_text")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class InstantJobSearchResult(BaseModel):
    title: str
    company: str | None = None
    location: str | None = None
    workplace_type: WorkplaceType = "unknown"
    url: HttpUrl
    snippet: str | None = None
    posted_at: datetime | None = None
    age_days: int | None = None
    age_text: str | None = None
    age_confidence: AgeConfidence = "unknown"
    score: int = 0
    reasons: list[str] = Field(default_factory=list)
    source_provider: SearchProvider = "brave_search"
    source_id: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Result title cannot be empty")
        return cleaned

    @field_validator("company", "location", "snippet", "age_text", "source_id")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_result(self) -> "InstantJobSearchResult":
        if self.age_days is not None and self.age_days < 0:
            raise ValueError("age_days cannot be negative")
        self.score = max(0, min(100, int(self.score)))
        self.reasons = [reason.strip() for reason in self.reasons if reason.strip()]
        return self


class InstantJobSearchRunSummary(BaseModel):
    requested_queries: list[InstantJobSearchQuery] = Field(default_factory=list)
    results: list[InstantJobSearchResult] = Field(default_factory=list)
    max_age_days: int = 7
    include_unknown_age: bool = False
    use_profile_matching: bool = False
    source_mode: SourceMode = "strict"
    total_raw_results: int = 0
    skipped_for_age: int = 0
    skipped_for_relevance: int = 0

    @model_validator(mode="after")
    def validate_counts(self) -> "InstantJobSearchRunSummary":
        if self.max_age_days < 1:
            raise ValueError("max_age_days must be at least 1")
        if self.total_raw_results < 0:
            raise ValueError("total_raw_results cannot be negative")
        if self.skipped_for_age < 0:
            raise ValueError("skipped_for_age cannot be negative")
        if self.skipped_for_relevance < 0:
            raise ValueError("skipped_for_relevance cannot be negative")
        return self
