from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

TICKETWEB_BASE = "https://www.ticketweb.com"
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
    base_url = "https://chopsuey.com"
    listing_url = "https://chopsuey.com/"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        # Ticketweb's venue page returns HTTP 530. The venue site embeds the
        # same upcoming shows in its own markup.
        r = session.get(self.listing_url, timeout=30)
        r.raise_for_status()
        events = self.parse_site(r.text, start)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    @classmethod
    def parse_site(cls, html: str, reference: datetime) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()
        local_reference = reference.astimezone(TZ) if reference.tzinfo else reference.replace(tzinfo=TZ)
        for row in soup.select(".tw-plugin-upcoming-event-list .row"):
            name = row.select_one(".tw-name a")
            date_node = row.select_one(".tw-event-date")
            time_node = row.select_one(".tw-event-time")
            if name is None or date_node is None or time_node is None:
                continue
            title = clean(name.get_text(" ", strip=True))
            date_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", clean(date_node.get_text(" ", strip=True)))
            time_match = TIME_RE.search(clean(time_node.get_text(" ", strip=True)))
            if not title or not date_match or not time_match:
                continue
            month = int(date_match.group(1))
            day = int(date_match.group(2))
            start_at = parse_datetime(f"{month}/{day}/{local_reference.year} {time_match.group('time')}")
            if start_at is None:
                continue
            if (local_reference.date() - start_at.date()).days > 30:
                start_at = parse_datetime(f"{month}/{day}/{local_reference.year + 1} {time_match.group('time')}")
            if start_at is None:
                continue
            event_url = urljoin(cls.base_url, name.get("href", ""))
            sid = f"{stable_source_id(cls.key, event_url, title)}:{start_at.strftime('%Y%m%dT%H%M')}"
            if sid in seen:
                continue
            seen.add(sid)
            doors_node = row.select_one(".tw-event-door-time")
            doors = clean(doors_node.get_text(" ", strip=True)).upper() if doors_node else None
            lower = title.casefold()
            image = row.select_one("img[src]")
            events.append(Event(
                id=f"{cls.key}:{sid}",
                source=cls.key,
                source_event_id=sid,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=event_url,
                ticket_url=event_url,
                image_url=image.get("src") if image else None,
                doors_time=doors or None,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "chop_suey_site"},
            ))
        return dedupe(events)

    @classmethod
    def parse_listing(cls, html: str, default_year: int | None = None) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # TicketWeb event inventory links are canonical /event/... URLs. Use
        # those links to define event cards, rather than flattening the page.
        candidates: dict[str, list[Tag]] = {}
        for a in soup.find_all("a", href=True):
            href = urljoin(TICKETWEB_BASE, a.get("href", ""))
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
                    href = urljoin(TICKETWEB_BASE, a.get("href", ""))
                    if "/event/" in urlparse(href).path.casefold() and "ticketweb.com" in urlparse(href).netloc.casefold():
                        urls.add(href)
                if urls == {event_url} and DATE_RE.search(text) and TIME_RE.search(text):
                    return parent
                node = parent
        return None
