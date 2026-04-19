"""Compatibility shim for job source registry."""

from jobtracker.job_tracking.sources.registry import SourceRegistry, build_default_registry

__all__ = ["SourceRegistry", "build_default_registry"]
