from __future__ import annotations

from pydantic import BaseModel, Field


class WebConfigSummary(BaseModel):
    default_query: str | None = None
    default_location: str | None = None
    max_age_days: int = 7
    include_unknown_age: bool = False
    default_limit: int = 25
    enabled_instant_search_sources: list[str] = Field(default_factory=list)


class InstantJobSearchApiRequest(BaseModel):
    query: str | None = None
    location: str | None = None
    days: int | None = Field(default=None, ge=1, le=90)
    limit: int = Field(default=25, ge=1, le=100)
    include_unknown_age: bool = False
