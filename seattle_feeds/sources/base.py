from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from requests import Session
from ..models import Event


class EventSource(ABC):
    key = ""
    name = ""
    allow_empty = False

    @abstractmethod
    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
        raise NotImplementedError


def dedupe(events: list[Event]) -> list[Event]:
    return list({event.id: event for event in events}.values())
