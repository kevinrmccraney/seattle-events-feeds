from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

DATE_TIME_RE = re.compile(
    r"\b(?P<date>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})\s+"
    r"(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)
FULL_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
    re.I,
)


class CrocodileCalendarSource(EventSource):
    base_url = "https://calendar.thecrocodile.com/"

    def __init__(self, key: str, name: str, venue: str):
        self.key = key
        self.name = name
        self.venue = venue

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.base_url, timeout=30)
        response.raise_for_status()
        events = self.parse_calendar(response.text)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    def parse_calendar(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # The current calendar exposes a compact event link whose text is
        # "TITLE Mon D, YYYY H:MM PM VENUE Buy Tickets". Parse that stable,
        # user-visible representation rather than depending on Webflow classes.
        for anchor in soup.find_all("a", href=True):
            text = clean(anchor.get_text(" ", strip=True))
            if not text or self.venue.casefold() not in text.casefold():
                continue
            match = DATE_TIME_RE.search(text)
            if not match:
                continue

            venue_pos = text.casefold().find(self.venue.casefold(), match.end())
            if venue_pos < 0:
                continue

            title = clean(text[:match.start()])
            if not title:
                continue

            start_at = parse_datetime(f"{match.group('date')} {match.group('time')}")
            if start_at is None:
                continue

            href = urljoin(self.base_url, anchor.get("href", ""))
            card = self._find_card(anchor)
            ticket_url = self._ticket_url(card) if card else None
            identity_url = ticket_url or href
            # When the ticket provider link is shared/generic, include venue and
            # title but not date in the fallback identity. Exact performance time
            # is appended because this calendar can list multiple same-title sets.
            base_id = stable_source_id(self.key, identity_url, f"{title}|{self.venue}")
            source_event_id = f"{base_id}:{start_at.strftime('%Y%m%dT%H%M')}"
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            lower = text.lower()
            events.append(Event(
                id=f"{self.key}:{source_event_id}",
                source=self.key,
                source_event_id=source_event_id,
                title=title,
                venue=self.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href or self.base_url,
                ticket_url=ticket_url or href or None,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "crocodile_calendar"},
            ))

        return dedupe(events)

    @staticmethod
    def _find_card(anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        for _ in range(8):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                return None
            text = clean(parent.get_text(" ", strip=True))
            if DATE_TIME_RE.search(text) and "Buy Tickets" in text:
                return parent
            node = parent
        return None

    @classmethod
    def _ticket_url(cls, card: Tag) -> str | None:
        for a in card.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            label = clean(a.get_text(" ", strip=True)).lower()
            if "buy tickets" in label and "thecrocodile.com" not in href:
                return href
        return None


def CrocodileSource() -> CrocodileCalendarSource:
    return CrocodileCalendarSource("crocodile", "The Crocodile", "The Crocodile")


def SunsetTavernSource() -> CrocodileCalendarSource:
    return CrocodileCalendarSource("sunset-tavern", "Sunset Tavern", "Sunset Tavern")


def BelltownYachtClubSource() -> CrocodileCalendarSource:
    return CrocodileCalendarSource("belltown-yacht-club", "Belltown Yacht Club", "Belltown Yacht Club")


def BabaYagaSource() -> CrocodileCalendarSource:
    return CrocodileCalendarSource("baba-yaga", "Baba Yaga", "Baba Yaga")
