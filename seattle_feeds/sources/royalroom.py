from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

DATE_TIME_RE = re.compile(
    r"(?P<date>(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+\d{4})\s+@\s+(?P<time>\d{1,2}:\d{2}\s+[AP]M)",
    re.I,
)


class RoyalRoomSource(EventSource):
    key = "royal-room"
    name = "The Royal Room"
    venue = "The Royal Room"
    base_url = "https://theroyalroomseattle.com"
    calendar_url = "https://theroyalroomseattle.com/events/"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.calendar_url, timeout=30)
        response.raise_for_status()
        events = self.parse_calendar(response.text)
        return dedupe(
            event for event in events
            if event.start_at >= start and (end is None or event.start_at <= end)
        )

    @classmethod
    def parse_calendar(cls, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            if "/event/" not in urlparse(href).path:
                continue

            container = cls._find_container(a)
            text = clean((container or a).get_text(" ", strip=True))
            if not text or "CLOSED FOR MAINTENANCE" in text.upper():
                continue

            match = DATE_TIME_RE.search(text)
            if not match:
                continue

            start_at = parse_datetime(f"{match.group('date')} {match.group('time')}")
            if start_at is None:
                continue

            title = cls._extract_title(text, match)
            if not title:
                title = clean(a.get_text(" ", strip=True))
                title = DATE_TIME_RE.sub("", title).strip(" -")
            if not title:
                continue

            slug = urlparse(href).path.rstrip("/").split("/")[-1]
            source_event_id = slug or stable_source_id(cls.key, href, title)
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            events.append(Event(
                id=f"{cls.key}:{source_event_id}",
                source=cls.key,
                source_event_id=source_event_id,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href,
                ticket_url=href,
                status="scheduled",
                sold_out="sold out" in text.lower(),
                metadata={"platform": "wordpress_events"},
            ))

        return dedupe(events)

    @classmethod
    def _find_container(cls, anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(8):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if DATE_TIME_RE.search(text):
                best = parent
                event_links = [x for x in parent.find_all("a", href=True) if "/event/" in urlparse(urljoin(cls.base_url, x.get("href", ""))).path]
                if len(event_links) == 1:
                    return parent
            node = parent
        return best

    @staticmethod
    def _extract_title(text: str, match: re.Match) -> str:
        before = text[:match.start()].strip()
        before = re.sub(r"^\d{1,2}\s+[A-Z][a-z]{2}\s+", "", before)
        return clean(before).strip(" -")
