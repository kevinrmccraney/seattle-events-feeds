from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .util import json_hash

MATERIAL_STATUSES = {"cancelled", "canceled", "postponed", "rescheduled"}


@dataclass(frozen=True)
class Event:
    id: str
    source: str
    source_event_id: str
    title: str
    venue: str
    start_at: datetime
    event_url: str
    end_at: datetime | None = None
    ticket_url: str | None = None
    image_url: str | None = None
    description: str | None = None
    support: str | None = None
    promoter: str | None = None
    doors_time: str | None = None
    age_restriction: str | None = None
    status: str = "scheduled"
    sold_out: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def material_payload(self) -> dict[str, Any]:
        status = self.status.lower().strip()
        return {
            "title": self.title,
            "artists": self.metadata.get("artists") or [],
            "support": self.support,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "venue": self.venue,
            # Sale-state changes such as sold_out/on-sale are intentionally not
            # material. Only changes that can alter the event itself are included.
            "event_status": status if status in MATERIAL_STATUSES else "scheduled",
        }

    def content_payload(self) -> dict[str, Any]:
        d = asdict(self)
        d["start_at"] = self.start_at.isoformat()
        d["end_at"] = self.end_at.isoformat() if self.end_at else None
        return d

    def row(self, seen_at: datetime) -> dict[str, Any]:
        d = self.content_payload()
        d["content_hash"] = json_hash(self.content_payload())
        d["material_hash"] = json_hash(self.material_payload())
        d["last_seen_at"] = seen_at.isoformat()
        d["missing_since"] = None
        d["removed"] = False
        return d


@dataclass(frozen=True)
class IngestionEvent:
    source: str
    level: str
    code: str
    message: str
    occurred_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def row(self) -> dict:
        return {
            "source": self.source,
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "first_seen_at": self.occurred_at.isoformat(),
            "last_seen_at": self.occurred_at.isoformat(),
            "metadata": self.metadata,
        }
