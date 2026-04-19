from __future__ import annotations

from jobtracker.company_discovery.base import CompanyDiscoveryAdapter
from jobtracker.company_discovery.common import (
    ensure_list_param,
    location_matches_query,
    text_matches_query,
    workplace_matches_query,
)
from jobtracker.config.models import CompanyDiscoverySourceDefinition
from jobtracker.models import CompanyDiscoveryQuery, RawCompanyDiscovery


class AustinEcosystemDiscoveryAdapter(CompanyDiscoveryAdapter):
    source_name = "austin_ecosystem"

    def discover(
        self,
        source: CompanyDiscoverySourceDefinition,
        query: CompanyDiscoveryQuery,
    ) -> list[RawCompanyDiscovery]:
        entries = ensure_list_param(source.params, "entries")
        discoveries: list[RawCompanyDiscovery] = []

        for entry in entries:
            company_name = str(entry["company_name"])
            location_text = str(entry.get("location_text", "") or "")
            workplace_type = str(entry.get("workplace_type", "unknown") or "unknown")
            searchable_text = " ".join(
                [
                    company_name,
                    str(entry.get("summary", "") or ""),
                    " ".join(str(item) for item in entry.get("tags", []) if item),
                    " ".join(str(item) for item in entry.get("role_focus", []) if item),
                ]
            )

            if not text_matches_query(searchable_text, query.keywords):
                continue
            if not location_matches_query(location_text, query.locations):
                continue
            if not workplace_matches_query(workplace_type, query.workplace_types):
                continue

            discoveries.append(
                RawCompanyDiscovery(
                    source_name=source.name,
                    source_type=source.type,
                    source_url=str(entry["source_url"]),
                    company_name=company_name,
                    company_url=entry.get("company_url"),
                    careers_url=entry.get("careers_url"),
                    job_title=entry.get("representative_role"),
                    location_text=location_text or None,
                    workplace_type=workplace_type,  # type: ignore[arg-type]
                    evidence_kind=str(entry.get("evidence_kind", "ecosystem_entry")),
                    raw_payload=entry,
                )
            )
        return discoveries
