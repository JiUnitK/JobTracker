from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobtracker.storage.orm import SourceORM
from jobtracker.storage.repository_utils import utc_now


class SourceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        name: str,
        reliability_tier: str,
        enabled: bool = True,
        base_url: str | None = None,
    ) -> SourceORM:
        source = self.session.scalar(select(SourceORM).where(SourceORM.name == name))
        if source is None:
            source = SourceORM(
                name=name,
                reliability_tier=reliability_tier,
                enabled=enabled,
                base_url=base_url,
            )
            self.session.add(source)
        else:
            source.reliability_tier = reliability_tier
            source.enabled = enabled
            source.base_url = base_url
        self.session.flush()
        return source

    def mark_success(self, name: str) -> SourceORM:
        source = self.session.scalar(select(SourceORM).where(SourceORM.name == name))
        if source is None:
            raise ValueError(f"Source '{name}' is not registered")
        source.last_success_at = utc_now()
        self.session.flush()
        return source

    def mark_error(self, name: str) -> SourceORM:
        source = self.session.scalar(select(SourceORM).where(SourceORM.name == name))
        if source is None:
            raise ValueError(f"Source '{name}' is not registered")
        source.last_error_at = utc_now()
        self.session.flush()
        return source

    def list_all(self) -> list[SourceORM]:
        return list(self.session.scalars(select(SourceORM).order_by(SourceORM.name)))
