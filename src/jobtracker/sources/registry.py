from __future__ import annotations

from jobtracker.sources.ashby import AshbyAdapter
from jobtracker.sources.base import SourceAdapter
from jobtracker.sources.greenhouse import GreenhouseAdapter
from jobtracker.sources.lever import LeverAdapter


class SourceRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters[adapter.source_name] = adapter

    def get(self, source_name: str) -> SourceAdapter | None:
        return self._adapters.get(source_name)

    def list_registered(self) -> list[str]:
        return sorted(self._adapters)


def build_default_registry() -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(GreenhouseAdapter())
    registry.register(LeverAdapter())
    registry.register(AshbyAdapter())
    return registry
