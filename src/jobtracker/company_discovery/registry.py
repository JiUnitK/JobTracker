from __future__ import annotations

from jobtracker.company_discovery.base import CompanyDiscoveryAdapter
from jobtracker.company_discovery.directory_adapter import CompanyDirectoryDiscoveryAdapter
from jobtracker.company_discovery.ecosystem_adapter import AustinEcosystemDiscoveryAdapter
from jobtracker.company_discovery.search_adapter import CompanySearchDiscoveryAdapter


class CompanyDiscoveryRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, CompanyDiscoveryAdapter] = {}

    def register(self, adapter: CompanyDiscoveryAdapter) -> None:
        self._adapters[adapter.source_name] = adapter

    def get(self, source_name: str) -> CompanyDiscoveryAdapter | None:
        return self._adapters.get(source_name)

    def list_registered(self) -> list[str]:
        return sorted(self._adapters)


def build_default_company_discovery_registry() -> CompanyDiscoveryRegistry:
    registry = CompanyDiscoveryRegistry()
    registry.register(CompanySearchDiscoveryAdapter())
    registry.register(AustinEcosystemDiscoveryAdapter())
    registry.register(CompanyDirectoryDiscoveryAdapter())
    return registry
