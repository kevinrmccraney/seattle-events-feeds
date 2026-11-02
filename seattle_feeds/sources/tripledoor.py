from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

DATETIME_RE = re.compile(
    r"\b(?P<date>(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+\d{4})\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)


class TripleDoorCalendarSource(EventSource):
    base_url = "https://tickets.thetripledoor.net/"
    listing_url = "https://tickets.thetripledoor.net/performancelisting.asp?venue=1&venuename=The+Triple+Door"

    def __init__(self, key: str, name: str, venue: str, rabbit_box: bool = False):
        self.key = key
        self.name = name
        self.venue = venue
        self.rabbit_box = rabbit_box

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.listing_url, timeout=30)
        response.raise_for_status()
        events = self.parse_listing(response.text)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    def parse_listing(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # Event detail links carry evt= IDs. The listing has one card per
        # performance, so combine the event ID with the exact performance time.
        for a in soup.find_all("a", href=True):
            href = urljoin(self.base_url, a.get("href", ""))
            if "eventperformances.asp" not in href or "evt=" not in href:
                continue
            title = clean(a.get_text(" ", strip=True))
            if not title:
                continue

            is_rabbit = "at the rabbit box" in title.casefold()
            if is_rabbit != self.rabbit_box:
                continue

            card = self._find_card(a)
            if card is None:
                continue
            text = clean(card.get_text(" ", strip=True))
            match = DATETIME_RE.search(text)
            if not match:
                continue
            start_at = parse_datetime(f"{match.group('date')} {match.group('time')}")
            if start_at is None:
                continue

            qs = parse_qs(urlparse(href).query)
            evt = (qs.get("evt") or [""])[0] or stable_source_id(self.key, href, title)
            source_event_id = f"{evt}:{start_at.strftime('%Y%m%dT%H%M')}"
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            clean_title = re.sub(r"\s+at The Rabbit Box\s*$", "", title, flags=re.I) if self.rabbit_box else title
            lower = text.lower()
            events.append(Event(
                id=f"{self.key}:{source_event_id}",
                source=self.key,
                source_event_id=source_event_id,
                title=clean_title,
                venue=self.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href,
                ticket_url=href,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "showare", "event_id": evt},
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
            if DATETIME_RE.search(text):
                best = parent
                links = [x for x in parent.find_all("a", href=True) if "eventperformances.asp" in x.get("href", "")]
                if len(links) == 1:
                    return parent
            node = parent
        return best


def TripleDoorSource() -> TripleDoorCalendarSource:
    return TripleDoorCalendarSource("triple-door", "The Triple Door", "The Triple Door", rabbit_box=False)


def RabbitBoxSource() -> TripleDoorCalendarSource:
    return TripleDoorCalendarSource("rabbit-box", "The Rabbit Box", "The Rabbit Box", rabbit_box=True)
