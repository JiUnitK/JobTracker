from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from jobtracker.config.models import SourceDefinition
from jobtracker.models import RawJobPosting, SearchQuery


class SourceAdapter(ABC):
    source_name: str

    @abstractmethod
    def collect(self, source: SourceDefinition, query: SearchQuery) -> list[RawJobPosting]:
        """Collect raw jobs for a source and query."""


@dataclass(slots=True)
class SourceRunResult:
    source_name: str
    query: SearchQuery
    raw_jobs: list[RawJobPosting] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors
