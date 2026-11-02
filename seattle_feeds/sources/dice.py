from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from dateutil.parser import isoparse
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import clean


class DiceVeraSource(EventSource):
    key = "vera"
    name = "The Vera Project / Black Lodge"
    endpoint = "https://partners-endpoint.dice.fm/api/v2/events"
    page_size = 24

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> Event:
        source_event_id = str(raw["id"])
        start_at = isoparse(raw["date"])
        end_at = isoparse(raw["date_end"]) if raw.get("date_end") else None
        doors_time = None
        for row in raw.get("lineup") or []:
            if clean(row.get("details")).lower() == "doors open":
                doors_time = clean(row.get("time")) or None
                break

        flags = raw.get("flags") or []
        sold_out = bool(raw.get("sold_out"))
        if "postponed" in flags:
            status = "postponed"
        elif "rescheduled" in flags:
            status = "rescheduled"
        elif sold_out:
            status = "sold_out"
        else:
            status = clean(raw.get("status")) or "scheduled"

        images = raw.get("event_images") or {}
        image_url = images.get("landscape") or ((raw.get("images") or [None])[0])
        artists = [clean(x) for x in (raw.get("artists") or []) if clean(x)]

        return Event(
            id=f"vera:{source_event_id}",
            source="vera",
            source_event_id=source_event_id,
            title=clean(raw.get("name")),
            venue=clean(raw.get("venue")) or "The Vera Project",
            start_at=start_at,
            end_at=end_at,
            event_url=clean(raw.get("url")),
            ticket_url=clean(raw.get("url")) or None,
            image_url=image_url,
            description=clean(raw.get("description")) or None,
            support=", ".join(artists[1:]) if len(artists) > 1 else None,
            promoter=clean(raw.get("presented_by")) or None,
            doors_time=doors_time,
            age_restriction=clean(raw.get("age_limit")) or None,
            status=status,
            sold_out=sold_out,
            metadata={
                "artists": artists,
                "genre_tags": raw.get("genre_tags") or [],
                "address": raw.get("address"),
                "flags": flags,
                "checksum": raw.get("checksum"),
            },
        )

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        api_key = self.api_key or os.environ.get("DICE_API_KEY")
        if not api_key:
            raise PermissionError("DICE_API_KEY is not configured")

        out: list[Event] = []
        page = 1
        while True:
            response = session.get(
                self.endpoint,
                params={
                    "filter[flags][]": ["going_ahead", "rescheduled", "postponed"],
                    "filter[venues][]": ["The Vera Project", "The Black Lodge"],
                    "page[number]": page,
                    "page[size]": self.page_size,
                    "types": "linkout,event",
                },
                headers={
                    "x-api-key": api_key,
                    "Origin": "https://theveraproject.org",
                    "Referer": "https://theveraproject.org/",
                },
                timeout=30,
            )
            if response.status_code in (401, 403):
                raise PermissionError(f"DICE API authentication failed (HTTP {response.status_code})")
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("data") or []
            if not batch:
                break

            for raw in batch:
                if "music:gig" not in (raw.get("type_tags") or []):
                    continue
                event = self._normalize(raw)
                if event.start_at >= start:
                    out.append(event)

            # We intentionally use page length rather than undocumented metadata.
            # Fetch every available page; display windows are a frontend concern.
            if len(batch) < self.page_size:
                break
            page += 1

        return dedupe(out)
