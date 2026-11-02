from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime

DATE_RE = re.compile(
    r"\b(?P<date>(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2}(?:,\s+\d{4})?)\s*@\s*(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)


class TripleDoorSource(EventSource):
    key = "triple-door"
    name = "The Triple Door"
    venue = "The Triple Door"
    base_url = "https://www.thetripledoor.net"
    listing_url = "https://www.thetripledoor.net/mainstage-calendar"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.listing_url, timeout=30)
        response.raise_for_status()

        links = self.extract_performance_links(response.text)
        events: list[Event] = []
        fallback_by_id = {e.source_event_id: e for e in self.parse_listing(response.text, default_year=start.year)}

        for href, occurrence_id in links:
            try:
                detail = session.get(href, timeout=30)
                detail.raise_for_status()
            except Exception:
                event = fallback_by_id.get(occurrence_id)
                if event is not None and event.start_at >= start and (end is None or event.start_at <= end):
                    events.append(event)
                continue

            event = self.parse_detail(detail.text, href, occurrence_id, default_year=start.year)
            if event is None:
                continue
            if event.start_at < start or (end is not None and event.start_at > end):
                continue
            events.append(event)

        return dedupe(events)


    @classmethod
    def parse_listing(cls, html: str, default_year: int | None = None) -> list[Event]:
        """Fallback parser for the calendar HTML itself.

        Live fetching now prefers first-party detail pages, but this parser keeps
        the calendar usable if the detail request fails and preserves regression
        coverage for the current compact card structure.
        """
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            if "/go/events/" not in href:
                continue
            qs = parse_qs(urlparse(href).query)
            occurrence_id = (qs.get("occurrence_id") or [""])[0]
            if not occurrence_id or occurrence_id in seen:
                continue

            node = a.parent
            card = node if node is not None else a
            text = clean(card.get_text(" ", strip=True))
            lower = text.casefold()
            if "the rabbit box" in lower or "mainstage theatre" not in lower:
                continue

            match = DATE_RE.search(text)
            if not match:
                continue
            date_text = match.group("date")
            if not re.search(r"\b20\d{2}\b", date_text):
                date_text = f"{date_text}, {default_year or datetime.now(TZ).year}"
            start_at = parse_datetime(f"{date_text} {match.group('time')}")
            if start_at is None:
                continue

            title = clean(a.get_text(" ", strip=True))
            if not title or title.casefold().startswith("closed for"):
                continue

            seen.add(occurrence_id)
            events.append(Event(
                id=f"{cls.key}:{occurrence_id}",
                source=cls.key,
                source_event_id=occurrence_id,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href,
                ticket_url=href,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "zoogle_calendar", "occurrence_id": occurrence_id},
            ))

        return dedupe(events)

    @classmethod
    def extract_performance_links(cls, html: str) -> list[tuple[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        found: list[tuple[str, str]] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            if "/go/events/" not in href:
                continue
            qs = parse_qs(urlparse(href).query)
            occurrence_id = (qs.get("occurrence_id") or [""])[0]
            if not occurrence_id or occurrence_id in seen:
                continue
            seen.add(occurrence_id)
            found.append((href, occurrence_id))

        return found

    @classmethod
    def parse_detail(
        cls,
        html: str,
        event_url: str,
        occurrence_id: str,
        default_year: int | None = None,
    ) -> Event | None:
        soup = BeautifulSoup(html, "html.parser")
        text = clean(soup.get_text(" ", strip=True))
        lower = text.casefold()

        # Rabbit Box performances appear on the Triple Door calendar but belong
        # in the Rabbit Box feed.
        if "the rabbit box" in lower:
            return None
        if "mainstage theatre" not in lower:
            return None

        match = DATE_RE.search(text)
        if not match:
            return None

        date_text = match.group("date")
        if not re.search(r"\b20\d{2}\b", date_text):
            date_text = f"{date_text}, {default_year or datetime.now(TZ).year}"
        start_at = parse_datetime(f"{date_text} {match.group('time')}")
        if start_at is None:
            return None

        title = cls._title(soup)
        if not title or title.casefold().startswith("closed for"):
            return None

        ticket_url = None
        for a in soup.find_all("a", href=True):
            label = clean(a.get_text(" ", strip=True)).casefold()
            href = urljoin(cls.base_url, a.get("href", ""))
            if "get tickets" in label or "tickets.thetripledoor.net" in href:
                ticket_url = href
                break

        return Event(
            id=f"{cls.key}:{occurrence_id}",
            source=cls.key,
            source_event_id=occurrence_id,
            title=title,
            venue=cls.venue,
            start_at=start_at.astimezone(TZ),
            event_url=event_url,
            ticket_url=ticket_url or event_url,
            status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
            sold_out="sold out" in lower,
            metadata={"platform": "zoogle_calendar", "occurrence_id": occurrence_id},
        )

    @staticmethod
    def _title(soup: BeautifulSoup) -> str | None:
        generic = {
            "upcoming mainstage shows",
            "the triple door",
            "mainstage calendar",
        }
        for tag in soup.find_all(["h1", "h2", "h3"]):
            value = clean(tag.get_text(" ", strip=True))
            if not value:
                continue
            if value.casefold() in generic:
                continue
            return value
        return None
