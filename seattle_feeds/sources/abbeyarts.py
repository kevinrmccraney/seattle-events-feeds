from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

DATE_RANGE_RE = re.compile(
    r"\b(?P<date>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}),\s+"
    r"(?P<start>\d{1,2}(?::\d{2})?\s*[ap]m)\s*-\s*"
    r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+)?"
    r"(?P<end>\d{1,2}(?::\d{2})?\s*[ap]m)\s+(?:PDT|PST)\b",
    re.I,
)


class AbbeyArtsCollectionSource(EventSource):
    collection_url = "https://collections.humanitix.com/all-events-fccb3a"

    def __init__(self, key: str, name: str, venue: str, aliases: tuple[str, ...]):
        self.key = key
        self.name = name
        self.venue = venue
        self.aliases = tuple(a.casefold() for a in aliases)

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.collection_url, timeout=30)
        response.raise_for_status()
        events = self.parse_collection(response.text, default_year=start.year)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    def parse_collection(self, html: str, default_year: int | None = None) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(self.collection_url, a.get("href", ""))
            if "events.humanitix.com/" not in href:
                continue
            text = clean(a.get_text(" ", strip=True))
            if not text or not any(alias in text.casefold() for alias in self.aliases):
                continue
            match = DATE_RANGE_RE.search(text)
            if not match:
                continue

            # Collection cards omit the year in some client-rendered variants;
            # use the current producer year only as a fallback.
            year_match = re.search(r"\b(20\d{2})\b", text)
            year = int(year_match.group(1)) if year_match else (default_year or datetime.now(TZ).year)
            start_at = parse_datetime(f"{match.group('date')}, {year} {match.group('start')}")
            if start_at is None:
                continue

            # Everything between the time-range and the venue label is the title.
            prefix_end = match.end()
            remainder = clean(text[prefix_end:])
            venue_pos = min((remainder.casefold().find(alias) for alias in self.aliases if alias in remainder.casefold()), default=-1)
            title = clean(remainder[:venue_pos]) if venue_pos >= 0 else remainder
            if not title:
                continue

            slug = urlparse(href).path.strip("/").split("/")[-1]
            source_event_id = slug or stable_source_id(self.key, href, title)
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
                event_url=href,
                ticket_url=href,
                status="cancelled" if "cancelled:" in lower or "canceled:" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "humanitix", "collection": "abbey-arts"},
            ))

        return dedupe(events)


def FremontAbbeySource() -> AbbeyArtsCollectionSource:
    return AbbeyArtsCollectionSource(
        "fremont-abbey",
        "Fremont Abbey Arts Center",
        "Fremont Abbey Arts Center",
        ("Fremont Abbey Arts Center", "@ FREMONT ABBEY"),
    )


def BallardHomesteadSource() -> AbbeyArtsCollectionSource:
    return AbbeyArtsCollectionSource(
        "ballard-homestead",
        "Ballard Homestead",
        "Ballard Homestead",
        ("Ballard Homestead", "@ BALLARD HOMESTEAD"),
    )
