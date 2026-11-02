from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


PERF_DATE_RE = re.compile(
    r"\b(?P<date>(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+\d{4})\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)
EVENT_ID_RE = re.compile(r"(?:evt|event|eventid)=(\d+)", re.I)


class TripleDoorSource(EventSource):
    key = "triple-door"
    name = "The Triple Door"
    venue = "The Triple Door"
    base_url = "https://tickets.thetripledoor.net"
    listing_url = (
        "https://tickets.thetripledoor.net/performancelisting.asp"
        "?venue=1&venuename=The+Triple+Door"
    )

    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
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
        return dedupe(
            e for e in events
            if e.start_at >= start and (end is None or e.start_at <= end)
        )

    @classmethod
    def parse_listing(cls, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # Prefer event/performance containers discovered around full datetime text.
        for text_node in soup.find_all(string=PERF_DATE_RE):
            block = cls._find_performance_block(text_node.parent)
            if block is None:
                continue

            text = clean(block.get_text(" ", strip=True))
            match = PERF_DATE_RE.search(text)
            if not match:
                continue

            title = cls._title(block, text, match)
            if not title:
                continue
            if "at The Rabbit Box" in title:
                continue

            start_at = parse_datetime(f"{match.group('date')} {match.group('time')}")
            if start_at is None:
                continue

            event_url = cls._event_url(block)
            ticket_url = cls._ticket_url(block) or event_url

            # Ticketing listing can repeat the same event title at multiple times,
            # so performance datetime is part of identity.
            event_match = EVENT_ID_RE.search(event_url or "")
            base_id = (
                event_match.group(1)
                if event_match
                else stable_source_id(cls.key, event_url or cls.listing_url, title)
            )
            source_event_id = f"{base_id}:{start_at.strftime('%Y%m%dT%H%M')}"
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            lower = text.casefold()
            events.append(Event(
                id=f"{cls.key}:{source_event_id}",
                source=cls.key,
                source_event_id=source_event_id,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=event_url or cls.listing_url,
                ticket_url=ticket_url,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "accesso_showare"},
            ))

        return dedupe(events)

    @staticmethod
    def _find_performance_block(node: Tag) -> Tag | None:
        current: Tag | None = node
        best: Tag | None = None
        for _ in range(12):
            parent = current.parent if current else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if PERF_DATE_RE.search(text):
                best = parent
                # Stop at the smallest container with exactly one performance date.
                if len(PERF_DATE_RE.findall(text)) == 1:
                    return parent
            current = parent
        return best

    @classmethod
    def _title(cls, block: Tag, text: str, date_match) -> str | None:
        # Prefer a heading or substantial event link.
        for tag in block.find_all(["h1", "h2", "h3", "h4"]):
            value = clean(tag.get_text(" ", strip=True))
            if value and "Upcoming Performances" not in value:
                return value

        for a in block.find_all("a", href=True):
            value = clean(a.get_text(" ", strip=True))
            if not value:
                continue
            lower = value.casefold()
            if lower in {"buy tickets", "sold out", "more info", "calendar view"}:
                continue
            if "google map" in lower:
                continue
            return value

        # Fallback: everything before the datetime, minus common venue labels.
        prefix = clean(text[:date_match.start()])
        prefix = re.sub(r"^The Triple Door\s+", "", prefix, flags=re.I)
        return prefix or None

    @classmethod
    def _event_url(cls, block: Tag) -> str | None:
        for a in block.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            label = clean(a.get_text(" ", strip=True)).casefold()
            if "eventperformances.asp" in href.lower():
                return href
            if "buy tickets" not in label and "performance" in href.lower():
                return href
        return None

    @classmethod
    def _ticket_url(cls, block: Tag) -> str | None:
        for a in block.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            label = clean(a.get_text(" ", strip=True)).casefold()
            if "buy tickets" in label or "eventperformances.asp" in href.lower():
                return href
        return None
