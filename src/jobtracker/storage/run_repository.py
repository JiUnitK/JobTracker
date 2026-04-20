from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from jobtracker.storage.orm import SearchRunORM
from jobtracker.storage.repository_utils import utc_now


class SearchRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def start(
        self,
        trigger_type: str = "manual",
        *,
        started_at: datetime | None = None,
    ) -> SearchRunORM:
        search_run = SearchRunORM(
            trigger_type=trigger_type,
            status="running",
            started_at=started_at or utc_now(),
        )
        self.session.add(search_run)
        self.session.flush()
        return search_run

    def complete(
        self,
        search_run: SearchRunORM,
        *,
        status: str,
        summary: dict,
        completed_at: datetime | None = None,
    ) -> SearchRunORM:
        search_run.status = status
        search_run.summary_json = summary
        search_run.completed_at = completed_at or utc_now()
        self.session.flush()
        return search_run
