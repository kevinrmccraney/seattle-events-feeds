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
SHOW_RE = re.compile(
    r"\b(?:Show|Showtime|Music|Performance|Music starts at|Trivia)\s*[:\-]?\s*"
    r"(\d{1,2}(?::\d{2})?\s*[ap]m)\b",
    re.I,
)
DOORS_RE = re.compile(r"\bDoors?\s*[:/\-]?\s*(\d{1,2}(?::\d{2})?\s*[ap]m)\b", re.I)
AGE_RE = re.compile(r"\b(All Ages|\d{1,2}\+)", re.I)
TICKET_RE = re.compile(
    r"https?://(?:tickets\.venuepilot\.com|tickets\.thetripledoor\.net|"
    r"(?:www\.)?eventbrite\.com|(?:www\.)?ticketweb\.com|app\.opendate\.io)/[^\s<>\"']+",
    re.I,
)


class RabbitBoxSource(EventSource):
    key = "rabbit-box"
    name = "The Rabbit Box"
    venue = "The Rabbit Box"
    listing_url = "https://www.therabbitboxseattle.com/events"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(
            self.listing_url,
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        events = self.parse_listing(response.text)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    @classmethod
    def parse_listing(cls, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for text_node in soup.find_all(string=DATE_RE):
            block = cls._find_event_block(text_node.parent)
            if block is None:
                continue
            text = clean(block.get_text(" ", strip=True))
            lower = text.casefold()
            if "the rabbit box theatre" not in lower:
                continue

            date_match = DATE_RE.search(text)
            show_match = SHOW_RE.search(text)
            range_match = TIME_RANGE_RE.search(text)
            time_text = show_match.group(1) if show_match else (range_match.group(1) if range_match else None)
            if not date_match or not time_text:
                continue

            start_at = parse_datetime(f"{date_match.group(0)} {time_text}")
            if start_at is None:
                continue

            title = cls._title(block)
            if not title:
                continue

            event_url = cls._event_url(block)
            source_event_id = urlparse(event_url).path.rstrip("/").split("/")[-1] if event_url else ""
            if not source_event_id:
                source_event_id = stable_source_id(cls.key, event_url or cls.listing_url, title)
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            doors = DOORS_RE.search(text)
            age = AGE_RE.search(text)
            ticket_url = None
            match = TICKET_RE.search(str(block))
            if match:
                ticket_url = match.group(0).rstrip(".,;)")

            events.append(Event(
                id=f"{cls.key}:{source_event_id}",
                source=cls.key,
                source_event_id=source_event_id,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=event_url or cls.listing_url,
                ticket_url=ticket_url,
                doors_time=clean(doors.group(1)).upper() if doors else None,
                age_restriction=clean(age.group(1)) if age else None,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "squarespace_events"},
            ))
        return dedupe(events)

    @staticmethod
    def _find_event_block(node: Tag) -> Tag | None:
        current: Tag | None = node
        best: Tag | None = None
        for _ in range(12):
            parent = current.parent if current else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if DATE_RE.search(text) and "The Rabbit Box Theatre" in text:
                best = parent
                if len(DATE_RE.findall(text)) == 1:
                    return parent
            current = parent
        return best

    @staticmethod
    def _title(block: Tag) -> str | None:
        for tag in block.find_all(["h1", "h2", "h3", "h4"]):
            value = clean(tag.get_text(" ", strip=True))
            if value and value.casefold() not in {"events", "the rabbit box"}:
                return value
        for a in block.find_all("a", href=True):
            value = clean(a.get_text(" ", strip=True))
            if len(value) > 3 and value.casefold() not in {"google calendar", "ics", "map"}:
                return value
        return None

    @classmethod
    def _event_url(cls, block: Tag) -> str | None:
        for a in block.find_all("a", href=True):
            href = urljoin(cls.listing_url, a.get("href", ""))
            path = urlparse(href).path.rstrip("/")
            if path.startswith("/events/") and path != "/events":
                return href
        return None
