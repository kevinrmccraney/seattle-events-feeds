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
    r"\b(?P<date>(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2}(?:,\s+\d{4})?)\s*@\s*(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)
OCCURRENCE_RE = re.compile(r"[?&]occurrence_id=(\d+)")


class TripleDoorSource(EventSource):
    key = "triple-door"
    name = "The Triple Door"
    venue = "The Triple Door"
    base_url = "https://www.thetripledoor.net"
    listing_url = "https://www.thetripledoor.net/mainstage-calendar"
    max_pages = 60

    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
        # The month grid only shows day numbers. The same page also contains a
        # paginated detail list with full dates. Crawl that detail pagination.
        url = self.listing_url
        seen_urls: set[str] = set()
        events: list[Event] = []

        browser_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/141.0 Safari/537.36"
            )
        }

        for _ in range(self.max_pages):
            if url in seen_urls:
                break
            seen_urls.add(url)

            response = session.get(url, timeout=30, headers=browser_headers)
            response.raise_for_status()

            page_events = self.parse_detail_list(response.text, default_year=start.year)
            events.extend(page_events)

            next_url = self.next_page_url(response.text)
            if not next_url:
                break
            url = next_url

        return dedupe(
            e for e in events
            if e.start_at >= start and (end is None or e.start_at <= end)
        )

    @classmethod
    def parse_detail_list(
        cls,
        html: str,
        default_year: int | None = None,
    ) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            if "/go/events/" not in href:
                continue

            title = clean(a.get_text(" ", strip=True))
            if not title or title.casefold().startswith("closed for"):
                continue

            block = cls._find_detail_block(a)
            if block is None:
                continue

            text = clean(block.get_text(" ", strip=True))
            lower = text.casefold()
            if "the rabbit box" in lower:
                continue
            if "mainstage theatre" not in lower:
                continue

            match = FULL_DATE_RE.search(text)
            if not match:
                continue

            date_text = match.group("date")
            if not re.search(r"\b20\d{2}\b", date_text):
                date_text = f"{date_text}, {default_year or datetime.now(TZ).year}"
            start_at = parse_datetime(f"{date_text} {match.group('time')}")
            if start_at is None:
                continue

            occurrence_match = OCCURRENCE_RE.search(href)
            source_event_id = (
                occurrence_match.group(1)
                if occurrence_match
                else stable_source_id(cls.key, href, title)
            )
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            ticket_url = None
            for link in block.find_all("a", href=True):
                candidate = urljoin(cls.base_url, link.get("href", ""))
                label = clean(link.get_text(" ", strip=True)).casefold()
                if "get tickets" in label or "tickets.thetripledoor.net" in candidate:
                    ticket_url = candidate
                    break

            events.append(Event(
                id=f"{cls.key}:{source_event_id}",
                source=cls.key,
                source_event_id=source_event_id,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href,
                ticket_url=ticket_url or href,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "zoogle_calendar"},
            ))

        return dedupe(events)

    @classmethod
    def next_page_url(cls, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            label = clean(a.get_text(" ", strip=True)).casefold()
            if label == "next":
                return urljoin(cls.base_url, a.get("href", ""))
        return None

    @staticmethod
    def _find_detail_block(anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(12):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if FULL_DATE_RE.search(text):
                best = parent
                links = [
                    x for x in parent.find_all("a", href=True)
                    if "/go/events/" in x.get("href", "")
                ]
                if len(links) <= 1:
                    return parent
            node = parent
        return best
