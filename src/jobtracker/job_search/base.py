from __future__ import annotations

from abc import ABC, abstractmethod

from jobtracker.config.models import InstantSearchSourceDefinition
from jobtracker.job_search.models import InstantJobSearchQuery, RawInstantSearchResult


class InstantJobSearchAdapter(ABC):
    source_name: str

    @abstractmethod
    def search(
        self,
        source: InstantSearchSourceDefinition,
        query: InstantJobSearchQuery,
    ) -> list[RawInstantSearchResult]:
        """Search for raw open-web job results for a planned query."""

