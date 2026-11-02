from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime

DATE_RE = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+20\d{2}\b",
    re.I,
)
TIME_RANGE_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[AP]M)\s+(\d{1,2}:\d{2}\s*[AP]M)\b", re.I)
DOORS_RE = re.compile(r"\bDoors?\s*[:/\-]?\s*(\d{1,2}(?::\d{2})?\s*[ap]m)\b", re.I)
AGE_RE = re.compile(r"\b(All Ages|\d{1,2}\+)", re.I)


class RabbitBoxSource(EventSource):
    key = "rabbit-box"
    name = "The Rabbit Box"
    venue = "The Rabbit Box"
    listing_url = "https://www.therabbitboxseattle.com/events"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        r = session.get(self.listing_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        events = self.parse_listing(r.text)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    @classmethod
    def parse_listing(cls, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # Squarespace gives every real event a canonical /events/<slug> link.
        # Anchor on those links first, then find the smallest enclosing block
        # containing exactly one event URL, one full date, and the venue label.
        event_links: dict[str, list[Tag]] = {}
        for a in soup.find_all("a", href=True):
            href = urljoin(cls.listing_url, a.get("href", ""))
            path = urlparse(href).path.rstrip("/")
            if path.startswith("/events/") and path != "/events":
                event_links.setdefault(href, []).append(a)

        for event_url, anchors in event_links.items():
            title = cls._title_for_url(anchors)
            if not title:
                continue
            block = cls._event_block(anchors, event_url)
            if block is None:
                continue
            text = clean(block.get_text(" ", strip=True))
            if "the rabbit box theatre" not in text.casefold():
                continue
            dm = DATE_RE.search(text)
            tm = TIME_RANGE_RE.search(text)
            if not dm or not tm:
                continue
            start_at = parse_datetime(f"{dm.group(0)} {tm.group(1)}")
            end_at = parse_datetime(f"{dm.group(0)} {tm.group(2)}")
            if start_at is None:
                continue

            slug = urlparse(event_url).path.rstrip("/").split("/")[-1]
            if slug in seen:
                continue
            seen.add(slug)

            doors = DOORS_RE.search(text)
            age = AGE_RE.search(text)
            ticket_url = None
            for a in block.find_all("a", href=True):
                href = urljoin(cls.listing_url, a.get("href", ""))
                if "tickets.venuepilot.com" in href or "tickets.thetripledoor.net" in href:
                    ticket_url = href
                    break

            lower = text.casefold()
            events.append(Event(
                id=f"{cls.key}:{slug}",
                source=cls.key,
                source_event_id=slug,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                end_at=end_at.astimezone(TZ) if end_at else None,
                event_url=event_url,
                ticket_url=ticket_url,
                doors_time=clean(doors.group(1)).upper() if doors else None,
                age_restriction=clean(age.group(1)) if age else None,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "squarespace_event_cards"},
            ))
        return dedupe(events)

    @staticmethod
    def _title_for_url(anchors: list[Tag]) -> str | None:
        banned = {"view event", "view event →", "map", "(map)", "google calendar", "ics", "tickets"}
        values = []
        for a in anchors:
            v = clean(a.get_text(" ", strip=True))
            if not v or v.casefold() in banned or v.casefold().startswith("view event"):
                continue
            values.append(v)
        return max(values, key=len) if values else None

    @classmethod
    def _event_block(cls, anchors: list[Tag], event_url: str) -> Tag | None:
        for anchor in anchors:
            node: Tag | None = anchor
            for _ in range(14):
                parent = node.parent if node else None
                if not isinstance(parent, Tag):
                    break
                text = clean(parent.get_text(" ", strip=True))
                urls = set()
                for a in parent.find_all("a", href=True):
                    href = urljoin(cls.listing_url, a.get("href", ""))
                    path = urlparse(href).path.rstrip("/")
                    if path.startswith("/events/") and path != "/events":
                        urls.add(href)
                if urls == {event_url} and DATE_RE.search(text) and "The Rabbit Box Theatre" in text:
                    return parent
                node = parent
        return None
