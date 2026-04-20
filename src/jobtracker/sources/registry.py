"""Compatibility shim for tracked-job source registry.

New code should import from :mod:`jobtracker.job_tracking.sources.registry`.
"""

from jobtracker.job_tracking.sources.registry import SourceRegistry, build_default_registry

__all__ = ["SourceRegistry", "build_default_registry"]
