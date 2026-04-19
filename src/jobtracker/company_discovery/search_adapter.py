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


class CompanySearchDiscoveryAdapter(CompanyDiscoveryAdapter):
    source_name = "company_search"

    def discover(
        self,
        source: CompanyDiscoverySourceDefinition,
        query: CompanyDiscoveryQuery,
    ) -> list[RawCompanyDiscovery]:
        results = ensure_list_param(source.params, "results")
        discoveries: list[RawCompanyDiscovery] = []

        for result in results:
            job_title = str(result.get("job_title", "") or "")
            location_text = str(result.get("location_text", "") or "")
            workplace_type = str(result.get("workplace_type", "unknown") or "unknown")
            searchable_text = " ".join(
                [
                    str(result.get("company_name", "") or ""),
                    job_title,
                    str(result.get("snippet", "") or ""),
                    " ".join(str(item) for item in result.get("tags", []) if item),
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
                    source_url=str(result["source_url"]),
                    company_name=str(result["company_name"]),
                    company_url=result.get("company_url"),
                    careers_url=result.get("careers_url"),
                    job_url=result.get("job_url"),
                    job_title=job_title or None,
                    location_text=location_text or None,
                    workplace_type=workplace_type,  # type: ignore[arg-type]
                    evidence_kind=str(result.get("evidence_kind", "job_result")),
                    raw_payload=result,
                )
            )
        return discoveries
