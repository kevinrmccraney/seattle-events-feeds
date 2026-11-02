from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

FULL_DATE_RE = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2}(?:,\s+20\d{2})?\s*@\s*\d{1,2}:\d{2}\s*[AP]M\b",
    re.I,
)


class TripleDoorSource(EventSource):
    key = "triple-door"
    name = "The Triple Door"
    venue = "The Triple Door"
    listing_url = "https://www.thetripledoor.net/mainstage-calendar"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        r = session.get(self.listing_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        events = self.parse_listing(r.text, default_year=start.year)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    @classmethod
    def parse_listing(cls, html: str, default_year: int | None = None) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # The mainstage calendar has canonical links for each occurrence. The
        # lower detail list contains full weekday/month/day/time + venue, so use
        # those detail blocks when available and ignore Rabbit Box/MQ entries.
        for a in soup.find_all("a", href=True):
            title = clean(a.get_text(" ", strip=True))
            if not title or title.casefold().startswith("closed for"):
                continue
            href = urljoin(cls.listing_url, a.get("href", ""))
            if "/go/events/" not in href:
                continue
            block = cls._detail_block(a)
            if block is None:
                continue
            text = clean(block.get_text(" ", strip=True))
            lower = text.casefold()
            if "mainstage theatre" not in lower or "rabbit box" in lower:
                continue
            dm = FULL_DATE_RE.search(text)
            if not dm:
                continue
            date_text = dm.group(0)
            if not re.search(r"\b20\d{2}\b", date_text):
                # Insert year before @ for the date parser.
                date_text = re.sub(r"\s*@\s*", f", {default_year or datetime.now(TZ).year} @ ", date_text, count=1)
            start_at = parse_datetime(date_text.replace(" @ ", " "))
            if start_at is None:
                continue

            query = parse_qs(urlparse(href).query)
            occ = (query.get("occurrence_id") or [""])[0]
            sid = occ or f"{stable_source_id(cls.key, href, title)}:{start_at.strftime('%Y%m%dT%H%M')}"
            if sid in seen:
                continue
            seen.add(sid)

            ticket_url = None
            for link in block.find_all("a", href=True):
                candidate = urljoin(cls.listing_url, link.get("href", ""))
                label = clean(link.get_text(" ", strip=True)).casefold()
                if "get tickets" in label or "tickets.thetripledoor.net" in candidate:
                    ticket_url = candidate
                    break

            events.append(Event(
                id=f"{cls.key}:{sid}",
                source=cls.key,
                source_event_id=sid,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href,
                ticket_url=ticket_url or href,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "zoogle_mainstage_calendar"},
            ))
        return dedupe(events)

    @staticmethod
    def _detail_block(anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best = None
        for _ in range(12):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if FULL_DATE_RE.search(text):
                best = parent
                event_links = [x for x in parent.find_all("a", href=True) if "/go/events/" in x.get("href", "")]
                if len(event_links) == 1:
                    return parent
            node = parent
        return best
