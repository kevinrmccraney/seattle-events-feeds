"""Sea Monster Lounge listings from the Wix event list on the homepage.

Each list item is one performance. The event URL often ends in a local
timestamp. When it does not, the start comes from the first clock time in
the item text.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, canonical_url, clean, parse_datetime, stable_source_id


EVENT_URL_TIME = re.compile(
    r"(?P<year>20\d{2})-(?P<month>\d{2})-(?P<day>\d{2})-(?P<hour>\d{2})-(?P<minute>\d{2})$"
)
TEXT_TIME = re.compile(
    r"\b(?P<date>[A-Z][a-z]{2} \d{1,2}, 20\d{2}),\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b"
)


class SeaMonsterSource(EventSource):
    key = "sea-monster"
    name = "Sea Monster Lounge"
    venue = "Sea Monster Lounge"
    url = "https://www.seamonsterlounge.com/"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.url, timeout=30)
        response.raise_for_status()
        events = self.parse_listing(response.text)
        return dedupe(
            event for event in events
            if event.start_at >= start and (end is None or event.start_at <= end)
        )

    @classmethod
    def parse_listing(cls, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()
        for item in soup.select('[data-hook="event-list-item"]'):
            title_node = item.select_one('[data-hook="ev-list-item-title"]')
            link = item.select_one('a[href*="/event-info/"]')
            if title_node is None or link is None:
                continue
            title = clean(title_node.get_text(" ", strip=True))
            href = link.get("href") or ""
            if not title or not href:
                continue
            event_url = canonical_url(href, cls.url)
            start_at = cls._start_at(event_url, clean(item.get_text(" ", strip=True)))
            if start_at is None:
                continue
            sid = f"{stable_source_id(cls.key, event_url, title)}:{start_at.strftime('%Y%m%dT%H%M')}"
            if sid in seen:
                continue
            seen.add(sid)
            lower = title.casefold()
            status = "scheduled"
            if "cancelled" in lower or "canceled" in lower:
                status = "cancelled"
            elif "postponed" in lower:
                status = "postponed"
            events.append(Event(
                id=f"{cls.key}:{sid}",
                source=cls.key,
                source_event_id=sid,
                title=title,
                venue=cls.venue,
                start_at=start_at,
                event_url=event_url,
                ticket_url=event_url,
                status=status,
                metadata={"platform": "wix_event_list"},
            ))
        return dedupe(events)

    @staticmethod
    def _start_at(event_url: str, text: str) -> datetime | None:
        path = urlparse(event_url).path.rstrip("/")
        match = EVENT_URL_TIME.search(path)
        if match:
            return datetime(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
                int(match.group("hour")),
                int(match.group("minute")),
                tzinfo=TZ,
            )
        found = TEXT_TIME.search(text)
        if not found:
            return None
        return parse_datetime(f"{found.group('date')} {found.group('time')}")
