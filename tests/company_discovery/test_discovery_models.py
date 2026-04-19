from __future__ import annotations

import pytest

from jobtracker.models import CompanyDiscoveryQuery, RawCompanyDiscovery


def test_company_discovery_query_requires_keywords() -> None:
    with pytest.raises(ValueError):
        CompanyDiscoveryQuery(keywords=["   "], locations=["Austin, TX"])


def test_raw_company_discovery_requires_company_name() -> None:
    with pytest.raises(ValueError):
        RawCompanyDiscovery(
            source_name="company_search",
            source_type="search",
            source_url="https://example.com/results/1",
            company_name="   ",
        )
