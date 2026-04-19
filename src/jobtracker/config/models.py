from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from jobtracker.models.domain import SourceType


WorkplaceType = Literal["remote", "hybrid", "onsite"]
ReliabilityTier = Literal["tier1", "tier2", "tier3"]


class SearchTermsConfig(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    workplace_types: list[WorkplaceType] = Field(default_factory=list)
    seniority: list[str] = Field(default_factory=list)


class SourceDefinition(BaseModel):
    name: str
    type: SourceType
    enabled: bool = True
    reliability_tier: ReliabilityTier
    base_url: HttpUrl | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class SourcesConfig(BaseModel):
    defaults: dict[str, int | float | str | bool] = Field(default_factory=dict)
    sources: list[SourceDefinition] = Field(default_factory=list)

    def enabled_sources(self) -> list[SourceDefinition]:
        return [source for source in self.sources if source.enabled]


class ScoringWeights(BaseModel):
    title_match: float = 0.0
    skill_match: float = 0.0
    location_match: float = 0.0
    seniority_match: float = 0.0
    freshness: float = 0.0
    source_confidence: float = 0.0


class ScoringConfig(BaseModel):
    fit_weights: ScoringWeights
    hiring_weights: ScoringWeights
    priority_mix: dict[str, float] = Field(default_factory=dict)


class ProfileConfig(BaseModel):
    target_titles: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    target_workplace_types: list[WorkplaceType] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    target_companies: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    search_terms: SearchTermsConfig
    sources: SourcesConfig
    scoring: ScoringConfig
    profile: ProfileConfig

    def summary(self) -> str:
        enabled_sources = sum(1 for source in self.sources.sources if source.enabled)
        return (
            f"{enabled_sources} enabled sources, "
            f"{len(self.search_terms.include)} search terms, "
            f"{len(self.profile.target_titles)} target titles"
        )


class DatabaseSettings(BaseModel):
    url: str = "sqlite:///jobtracker.db"
    echo: bool = False

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")

    @property
    def sqlite_path(self) -> Path | None:
        if self.url == "sqlite:///:memory:":
            return None
        sqlite_prefix = "sqlite:///"
        if self.url.startswith(sqlite_prefix):
            return Path(self.url.removeprefix(sqlite_prefix))
        return None

    @model_validator(mode="after")
    def validate_sqlite_path(self) -> "DatabaseSettings":
        path = self.sqlite_path
        if path is not None and not path.name:
            raise ValueError("SQLite database URL must point to a file")
        return self
