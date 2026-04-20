from __future__ import annotations

from jobtracker.job_search.base import InstantJobSearchAdapter
from jobtracker.job_search.brave_adapter import BraveSearchAdapter


class InstantJobSearchRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, InstantJobSearchAdapter] = {}

    def register(self, adapter: InstantJobSearchAdapter) -> None:
        self._adapters[adapter.source_name] = adapter

    def get(self, source_name: str) -> InstantJobSearchAdapter | None:
        return self._adapters.get(source_name)


def build_default_instant_job_search_registry() -> InstantJobSearchRegistry:
    registry = InstantJobSearchRegistry()
    registry.register(BraveSearchAdapter())
    return registry

