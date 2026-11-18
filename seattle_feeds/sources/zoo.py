"""Woodland Park Zoo listings from the public events API.

The feed includes repeating public programs such as WildLanterns. Closure
notices, including early closures, are omitted.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, canonical_url, clean, stable_source_id


API_URL = "https://zoo.org/wp-json/tribe/events/v1/events"
MAX_PAGES = 8
CLOSURE_RE = re.compile(r"\b(?:closures?|closed)\b", re.I)


def is_closure(title: str) -> bool:
    return bool(CLOSURE_RE.search(title or ""))


class WoodlandParkZooSource(EventSource):
    key = "woodland-park-zoo"
    name = "Woodland Park Zoo"
    venue = "Woodland Park Zoo"
    url = "https://zoo.org/events/"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        local_start = start.astimezone(TZ) if start.tzinfo else start.replace(tzinfo=TZ)
        url = API_URL
        params = {"per_page": 50, "start_date": local_start.date().isoformat()}
        events: list[Event] = []
        for _ in range(MAX_PAGES):
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                break
            events.extend(self.events_from_payload(body))
            url = body.get("next_rest_url") or ""
            params = None
            if not url:
                break
        return dedupe(
            event for event in events
            if event.start_at >= local_start and (end is None or event.start_at <= end)
        )

    @classmethod
    def events_from_payload(cls, body: dict) -> list[Event]:
        events: list[Event] = []
        for item in body.get("events") or []:
            event = cls._event(item)
            if event is not None:
                events.append(event)
        return events

    @classmethod
    def _event(cls, item: dict) -> Event | None:
        if not isinstance(item, dict):
            return None
        if item.get("status") not in (None, "publish"):
            return None
        if item.get("hide_from_listings"):
            return None
        title = clean(item.get("title"))
        if not title or is_closure(title):
            return None
        start_at = _start_at(item)
        if start_at is None:
            return None
        event_url = canonical_url(item.get("url") or "", cls.url)
        if not event_url:
            return None
        sid = f"{stable_source_id(cls.key, event_url, title)}:{start_at.strftime('%Y%m%dT%H%M')}"
        venue_name = cls.venue
        venue = item.get("venue")
        if isinstance(venue, dict) and clean(venue.get("venue")):
            venue_name = clean(venue.get("venue"))
        image = item.get("image")
        image_url = image.get("url") if isinstance(image, dict) else None
        lower = title.casefold()
        age = "21+" if "21+" in title else None
        return Event(
            id=f"{cls.key}:{sid}",
            source=cls.key,
            source_event_id=sid,
            title=title,
            venue=venue_name,
            start_at=start_at,
            event_url=event_url,
            ticket_url=event_url,
            image_url=image_url or None,
            description=_plain(item.get("excerpt")),
            age_restriction=age,
            status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
            metadata={"platform": "woodland_park_zoo", "zoo_event_id": item.get("id")},
        )


def _start_at(item: dict) -> datetime | None:
    utc_text = item.get("utc_start_date")
    if utc_text:
        try:
            utc = datetime.fromisoformat(str(utc_text).replace(" ", "T")).replace(tzinfo=timezone.utc)
            return utc.astimezone(TZ)
        except ValueError:
            return None
    local_text = item.get("start_date")
    if not local_text:
        return None
    try:
        local = datetime.fromisoformat(str(local_text).replace(" ", "T"))
    except ValueError:
        return None
    if local.tzinfo is None:
        local = local.replace(tzinfo=TZ)
    return local.astimezone(TZ)


def _plain(value) -> str | None:
    if not value:
        return None
    text = clean(BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True))
    return text or None
