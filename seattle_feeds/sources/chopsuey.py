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
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2})(?:,?\s+(?P<year>20\d{2}))?\b",
    re.I,
)
TIME_RE = re.compile(r"\b(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b", re.I)
DOORS_RE = re.compile(r"\bDoors?\s*(?P<doors>\d{1,2}:\d{2}\s*[AP]M)\b", re.I)


class ChopSueySource(EventSource):
    key = "chop-suey"
    name = "Chop Suey"
    venue = "Chop Suey"
    base_url = "https://www.ticketweb.com"
    listing_url = "https://www.ticketweb.com/venue/chop-suey-seattle-wa/19270"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        r = session.get(self.listing_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        events = self.parse_listing(r.text, start.year)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    @classmethod
    def parse_listing(cls, html: str, default_year: int | None = None) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # TicketWeb event inventory links are canonical /event/... URLs. Use
        # those links to define event cards, rather than flattening the page.
        candidates: dict[str, list[Tag]] = {}
        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            path = urlparse(href).path.casefold()
            if "/event/" in path and "ticketweb.com" in urlparse(href).netloc.casefold():
                candidates.setdefault(href, []).append(a)

        for event_url, anchors in candidates.items():
            title = cls._title(anchors)
            if not title:
                continue
            block = cls._card(anchors, event_url)
            if block is None:
                continue
            text = clean(block.get_text(" ", strip=True))
            dm = DATE_RE.search(text)
            tm = TIME_RE.search(text)
            if not dm or not tm:
                continue
            year = int(dm.group("year")) if dm.group("year") else (default_year or datetime.now(TZ).year)
            start_at = parse_datetime(f"{dm.group('mon')} {dm.group('day')}, {year} {tm.group('time')}")
            if start_at is None:
                continue

            sid_base = stable_source_id(cls.key, event_url, title)
            sid = f"{sid_base}:{start_at.strftime('%Y%m%dT%H%M')}"
            if sid in seen:
                continue
            seen.add(sid)
            doors = DOORS_RE.search(text)
            lower = text.casefold()
            events.append(Event(
                id=f"{cls.key}:{sid}",
                source=cls.key,
                source_event_id=sid,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=event_url,
                ticket_url=event_url,
                doors_time=clean(doors.group('doors')).upper() if doors else None,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "ticketweb_event_cards"},
            ))
        return dedupe(events)

    @staticmethod
    def _title(anchors: list[Tag]) -> str | None:
        banned = {"find tickets", "buy tickets", "tickets", "more info", "view event"}
        values = []
        for a in anchors:
            v = clean(a.get_text(" ", strip=True))
            if v and v.casefold() not in banned:
                values.append(v)
        return max(values, key=len) if values else None

    @classmethod
    def _card(cls, anchors: list[Tag], event_url: str) -> Tag | None:
        for anchor in anchors:
            node: Tag | None = anchor
            for _ in range(12):
                parent = node.parent if node else None
                if not isinstance(parent, Tag):
                    break
                text = clean(parent.get_text(" ", strip=True))
                urls = set()
                for a in parent.find_all("a", href=True):
                    href = urljoin(cls.base_url, a.get("href", ""))
                    if "/event/" in urlparse(href).path.casefold() and "ticketweb.com" in urlparse(href).netloc.casefold():
                        urls.add(href)
                if urls == {event_url} and DATE_RE.search(text) and TIME_RE.search(text):
                    return parent
                node = parent
        return None
