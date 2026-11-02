from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

DATE_RE = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+\d{4}\b",
    re.I,
)
TIME_RANGE_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[AP]M)\s+(\d{1,2}:\d{2}\s*[AP]M)\b", re.I)
SHOW_RE = re.compile(r"\b(?:Show|Music|Performance|Music starts at)\s*[:\-]?\s*(\d{1,2}(?::\d{2})?\s*[ap]m)\b", re.I)
DOORS_RE = re.compile(r"\bDoors\s*[:\-]?\s*(\d{1,2}(?::\d{2})?\s*[ap]m)\b", re.I)
AGE_RE = re.compile(r"\b(All Ages|\d{1,2}\+)\b", re.I)


class RabbitBoxSource(EventSource):
    key = "rabbit-box"
    name = "The Rabbit Box"
    venue = "The Rabbit Box"
    base_url = "https://www.therabbitboxseattle.com"
    listing_url = "https://www.therabbitboxseattle.com/events"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.listing_url, timeout=30)
        response.raise_for_status()
        events = self.parse_listing(response.text)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    @classmethod
    def parse_listing(cls, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            if "/events/" not in urlparse(href).path:
                continue
            title = clean(a.get_text(" ", strip=True))
            if not title or title.casefold() in {"view event →", "back to all events"}:
                continue

            card = cls._find_card(a)
            if card is None:
                continue
            text = clean(card.get_text(" ", strip=True))
            if "The Rabbit Box Theatre" not in text:
                continue

            date_match = DATE_RE.search(text)
            if not date_match:
                continue
            show_match = SHOW_RE.search(text)
            range_match = TIME_RANGE_RE.search(text)
            time_text = show_match.group(1) if show_match else (range_match.group(1) if range_match else None)
            if not time_text:
                continue
            start_at = parse_datetime(f"{date_match.group(0)} {time_text}")
            if start_at is None:
                continue

            slug = urlparse(href).path.rstrip("/").split("/")[-1]
            source_event_id = slug or stable_source_id(cls.key, href, title)
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            doors = DOORS_RE.search(text)
            age = AGE_RE.search(text)
            ticket_url = cls._ticket_url(card)
            lower = text.casefold()
            events.append(Event(
                id=f"{cls.key}:{source_event_id}",
                source=cls.key,
                source_event_id=source_event_id,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href,
                ticket_url=ticket_url,
                doors_time=clean(doors.group(1)).upper() if doors else None,
                age_restriction=clean(age.group(1)) if age else None,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "squarespace_events"},
            ))

        return dedupe(events)

    @staticmethod
    def _find_card(anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(12):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if DATE_RE.search(text) and "The Rabbit Box Theatre" in text:
                best = parent
                links = [x for x in parent.find_all("a", href=True) if "/events/" in x.get("href", "")]
                if len(links) <= 2:
                    return parent
            node = parent
        return best

    @classmethod
    def _ticket_url(cls, card: Tag) -> str | None:
        for a in card.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            if any(host in href for host in ("tickets.venuepilot.com", "tickets.thetripledoor.net", "eventbrite.com", "app.opendate.io")):
                return href
        return None
