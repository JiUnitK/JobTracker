from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


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
    type: str
    enabled: bool = True
    reliability_tier: ReliabilityTier
    base_url: HttpUrl | None = None


class SourcesConfig(BaseModel):
    defaults: dict[str, int | float | str | bool] = Field(default_factory=dict)
    sources: list[SourceDefinition] = Field(default_factory=list)


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
