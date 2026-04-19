from __future__ import annotations

from abc import ABC, abstractmethod

from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.models import CompanyDiscoveryQuery, RawCompanyDiscovery


class CompanyDiscoveryAdapter(ABC):
    source_name: str

    @abstractmethod
    def discover(
        self,
        source: CompanyDiscoverySourceDefinition,
        query: CompanyDiscoveryQuery,
    ) -> list[RawCompanyDiscovery]:
        """Discover companies for a source and query."""
