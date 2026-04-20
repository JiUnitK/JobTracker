from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from jobtracker.models.domain import DiscoverySourceType, SourceType


WorkplaceType = Literal["remote", "hybrid", "onsite"]
ReliabilityTier = Literal["tier1", "tier2", "tier3"]
InstantSearchSourceType = Literal["search"]


class InstantJobSearchConfig(BaseModel):
    max_age_days: int = 7
    include_unknown_age: bool = False
    queries: list[str] = Field(default_factory=list)
    query_templates: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_search_settings(self) -> "InstantJobSearchConfig":
        if self.max_age_days < 1:
            raise ValueError("instant_job_search.max_age_days must be at least 1")
        cleaned_queries = [item.strip() for item in self.queries if item.strip()]
        cleaned_templates = [item.strip() for item in self.query_templates if item.strip()]
        self.queries = cleaned_queries
        self.query_templates = cleaned_templates
        return self


class CompanyDiscoveryQueryConfig(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    workplace_types: list[WorkplaceType] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_keywords(self) -> "CompanyDiscoveryQueryConfig":
        cleaned = [item.strip() for item in self.keywords if item.strip()]
        if not cleaned:
            raise ValueError("At least one keyword is required for a discovery query")
        self.keywords = cleaned
        return self


class SearchTermsConfig(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    workplace_types: list[WorkplaceType] = Field(default_factory=list)
    seniority: list[str] = Field(default_factory=list)
    instant_job_search: InstantJobSearchConfig = Field(
        default_factory=InstantJobSearchConfig
    )
    discovery_queries: list[CompanyDiscoveryQueryConfig] = Field(default_factory=list)


class SourceDefinition(BaseModel):
    name: str
    type: SourceType
    enabled: bool = True
    reliability_tier: ReliabilityTier
    base_url: HttpUrl | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class CompanyDiscoverySourceDefinition(BaseModel):
    name: str
    type: DiscoverySourceType
    enabled: bool = True
    base_url: HttpUrl | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class InstantSearchSourceDefinition(BaseModel):
    name: str
    type: InstantSearchSourceType
    enabled: bool = True
    base_url: HttpUrl | None = None
    api_key_env: str = "BRAVE_SEARCH_API_KEY"
    params: dict[str, Any] = Field(default_factory=dict)


class SourcesConfig(BaseModel):
    defaults: dict[str, int | float | str | bool] = Field(default_factory=dict)
    sources: list[SourceDefinition] = Field(default_factory=list)
    discovery_sources: list[CompanyDiscoverySourceDefinition] = Field(default_factory=list)
    instant_search_sources: list[InstantSearchSourceDefinition] = Field(default_factory=list)

    def enabled_sources(self) -> list[SourceDefinition]:
        return [source for source in self.sources if source.enabled]

    def enabled_discovery_sources(self) -> list[CompanyDiscoverySourceDefinition]:
        return [source for source in self.discovery_sources if source.enabled]

    def enabled_instant_search_sources(self) -> list[InstantSearchSourceDefinition]:
        return [source for source in self.instant_search_sources if source.enabled]


class CompanyDiscoveryScoringWeights(BaseModel):
    title_match: float = 0.4
    skill_match: float = 0.25
    location_match: float = 0.35
    repeated_appearance: float = 0.35
    ats_confidence: float = 0.35
    fresh_evidence: float = 0.3


class CompanyDiscoveryScoringConfig(BaseModel):
    fit_weights: CompanyDiscoveryScoringWeights = Field(
        default_factory=lambda: CompanyDiscoveryScoringWeights(
            title_match=0.4,
            skill_match=0.25,
            location_match=0.35,
            repeated_appearance=0.0,
            ats_confidence=0.0,
            fresh_evidence=0.0,
        )
    )
    hiring_weights: CompanyDiscoveryScoringWeights = Field(
        default_factory=lambda: CompanyDiscoveryScoringWeights(
            title_match=0.0,
            skill_match=0.0,
            location_match=0.0,
            repeated_appearance=0.35,
            ats_confidence=0.35,
            fresh_evidence=0.3,
        )
    )
    priority_mix: dict[str, float] = Field(
        default_factory=lambda: {"fit_score": 0.5, "hiring_score": 0.5}
    )


class ScoringWeights(BaseModel):
    title_match: float = 0.0
    skill_match: float = 0.0
    location_match: float = 0.0
    seniority_match: float = 0.0
    freshness: float = 0.0
    source_confidence: float = 0.0
    repeated_observations: float = 0.0
    related_openings: float = 0.0


class ScoringConfig(BaseModel):
    fit_weights: ScoringWeights
    hiring_weights: ScoringWeights
    priority_mix: dict[str, float] = Field(default_factory=dict)
    company_discovery: CompanyDiscoveryScoringConfig = Field(
        default_factory=CompanyDiscoveryScoringConfig
    )


class CompanyDiscoveryConfig(BaseModel):
    queries: list[CompanyDiscoveryQueryConfig] = Field(default_factory=list)
    sources: list[CompanyDiscoverySourceDefinition] = Field(default_factory=list)
    scoring: CompanyDiscoveryScoringConfig = Field(default_factory=CompanyDiscoveryScoringConfig)

    def enabled_sources(self) -> list[CompanyDiscoverySourceDefinition]:
        return [source for source in self.sources if source.enabled]


class JobSearchConfig(BaseModel):
    settings: InstantJobSearchConfig = Field(default_factory=InstantJobSearchConfig)
    sources: list[InstantSearchSourceDefinition] = Field(default_factory=list)

    def enabled_sources(self) -> list[InstantSearchSourceDefinition]:
        return [source for source in self.sources if source.enabled]


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
    company_discovery: CompanyDiscoveryConfig
    job_search: JobSearchConfig
    scoring: ScoringConfig
    profile: ProfileConfig

    def summary(self) -> str:
        enabled_sources = sum(1 for source in self.sources.sources if source.enabled)
        enabled_discovery_sources = sum(
            1 for source in self.company_discovery.sources if source.enabled
        )
        enabled_instant_search_sources = sum(
            1 for source in self.job_search.sources if source.enabled
        )
        return (
            f"{enabled_sources} enabled sources, "
            f"{enabled_discovery_sources} enabled discovery sources, "
            f"{enabled_instant_search_sources} enabled instant search sources, "
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
