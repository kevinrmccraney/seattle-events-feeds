from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

DATE_RE = re.compile(
    r"\b(?P<date>(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2}(?:,\s+\d{4})?)\s*@\s*(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)
COMPACT_RE = re.compile(
    r"\b(?P<date>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:,\s+\d{4})?)\s*@\s*(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)


class TripleDoorSource(EventSource):
    key = "triple-door"
    name = "The Triple Door"
    venue = "The Triple Door"
    base_url = "https://www.thetripledoor.net"
    listing_url = "https://www.thetripledoor.net/mainstage-calendar"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.listing_url, timeout=30)
        response.raise_for_status()
        events = self.parse_listing(response.text, default_year=start.year)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    @classmethod
    def parse_listing(cls, html: str, default_year: int | None = None) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # Each actual performance is linked through /go/events/... and carries
        # an occurrence_id query parameter that is stable for that performance.
        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            if "/go/events/" not in href:
                continue

            qs = parse_qs(urlparse(href).query)
            occurrence_id = (qs.get("occurrence_id") or [""])[0]
            if not occurrence_id or occurrence_id in seen:
                continue

            card = cls._find_card(a)
            if card is None:
                continue
            text = clean(card.get_text(" ", strip=True))
            lower = text.casefold()
            if "mainstage theatre" not in lower:
                # Rabbit Box performances also appear on this calendar; they
                # are handled by the first-party Rabbit Box feed instead.
                continue

            match = DATE_RE.search(text) or COMPACT_RE.search(text)
            if not match:
                continue
            date_text = match.group("date")
            if not re.search(r"\b20\d{2}\b", date_text):
                date_text = f"{date_text}, {default_year or datetime.now(TZ).year}"
            start_at = parse_datetime(f"{date_text} {match.group('time')}")
            if start_at is None:
                continue

            title = cls._title(a, card)
            if not title or title.casefold() == "closed for a private event":
                continue

            seen.add(occurrence_id)
            events.append(Event(
                id=f"{cls.key}:{occurrence_id}",
                source=cls.key,
                source_event_id=occurrence_id,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href,
                ticket_url=href,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "zoogle_calendar", "occurrence_id": occurrence_id},
            ))

        return dedupe(events)

    @staticmethod
    def _find_card(anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(10):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            event_links = [x for x in parent.find_all("a", href=True) if "/go/events/" in x.get("href", "")]
            # Once we have climbed into a container holding multiple event
            # occurrences, stop; otherwise one Rabbit Box card can inherit
            # Mainstage text from a neighboring card.
            if len(event_links) > 1:
                break
            if "Mainstage Theatre" in text and ("@" in text or re.search(r"\d{1,2}:\d{2}\s*[AP]M", text, re.I)):
                best = parent
                return parent
            node = parent
        return best

    @staticmethod
    def _title(anchor: Tag, card: Tag) -> str | None:
        value = clean(anchor.get_text(" ", strip=True))
        if value and "Mainstage Theatre" not in value and not re.search(r"\d{1,2}:\d{2}\s*[AP]M", value, re.I):
            return value
        for tag in card.find_all(["h2", "h3", "h4"]):
            value = clean(tag.get_text(" ", strip=True))
            if value and value.casefold() not in {"mainstage theatre", "get tickets"}:
                return value
        return None
