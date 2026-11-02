from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
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
    r"\b(?:Show|Showtime|Music|Performance|Music starts at)\s*[:\-]?\s*"
    r"(\d{1,2}(?::\d{2})?\s*[ap]m)\b",
    re.I,
)
DOORS_RE = re.compile(r"\bDoors\s*[:\-]?\s*(\d{1,2}(?::\d{2})?\s*[ap]m)\b", re.I)
AGE_RE = re.compile(r"\b(All Ages|\d{1,2}\+)", re.I)


class RabbitBoxSource(EventSource):
    key = "rabbit-box"
    name = "The Rabbit Box"
    venue = "The Rabbit Box"
    base_url = "https://www.therabbitboxseattle.com"
    listing_url = "https://www.therabbitboxseattle.com/events"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.listing_url, timeout=30)
        response.raise_for_status()

        links = self.extract_event_links(response.text)
        events: list[Event] = []
        fallback_by_url = {e.event_url: e for e in self.parse_listing(response.text)}
        for href in links:
            try:
                detail = session.get(href, timeout=30)
                detail.raise_for_status()
            except Exception:
                event = fallback_by_url.get(href)
                if event is not None and event.start_at >= start and (end is None or event.start_at <= end):
                    events.append(event)
                continue
            event = self.parse_detail(detail.text, href)
            if event is None:
                continue
            if event.start_at < start or (end is not None and event.start_at > end):
                continue
            events.append(event)

        return dedupe(events)


    @classmethod
    def parse_listing(cls, html: str) -> list[Event]:
        """Parse complete event containers from the listing as a fallback."""
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            path = urlparse(href).path.rstrip("/")
            if not path.startswith("/events/") or path == "/events":
                continue

            node = a
            card = None
            for _ in range(8):
                parent = node.parent if node else None
                if parent is None:
                    break
                text = clean(parent.get_text(" ", strip=True))
                if DATE_RE.search(text) and "The Rabbit Box Theatre" in text:
                    card = parent
                    break
                node = parent
            if card is None:
                continue

            text = clean(card.get_text(" ", strip=True))
            date_match = DATE_RE.search(text)
            show_match = SHOW_RE.search(text)
            range_match = TIME_RANGE_RE.search(text)
            time_text = show_match.group(1) if show_match else (range_match.group(1) if range_match else None)
            if not date_match or not time_text:
                continue

            start_at = parse_datetime(f"{date_match.group(0)} {time_text}")
            if start_at is None:
                continue

            title = clean(a.get_text(" ", strip=True))
            if not title or title.casefold() == "view event →":
                continue

            slug = path.split("/")[-1]
            if slug in seen:
                continue
            seen.add(slug)

            doors = DOORS_RE.search(text)
            age = AGE_RE.search(text)
            ticket_url = None
            for link in card.find_all("a", href=True):
                candidate = urljoin(cls.base_url, link.get("href", ""))
                if any(host in candidate for host in (
                    "tickets.venuepilot.com",
                    "tickets.thetripledoor.net",
                    "eventbrite.com",
                    "app.opendate.io",
                    "ticketweb.com",
                )):
                    ticket_url = candidate
                    break

            lower = text.casefold()
            events.append(Event(
                id=f"{cls.key}:{slug}",
                source=cls.key,
                source_event_id=slug,
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

    @classmethod
    def extract_event_links(cls, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        found: list[str] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            path = urlparse(href).path.rstrip("/")
            if not path.startswith("/events/"):
                continue
            if path == "/events":
                continue
            if href in seen:
                continue
            seen.add(href)
            found.append(href)
        return found

    @classmethod
    def parse_detail(cls, html: str, event_url: str) -> Event | None:
        soup = BeautifulSoup(html, "html.parser")
        text = clean(soup.get_text(" ", strip=True))
        lower = text.casefold()

        if "the rabbit box theatre" not in lower:
            return None

        date_match = DATE_RE.search(text)
        if not date_match:
            return None

        show_match = SHOW_RE.search(text)
        range_match = TIME_RANGE_RE.search(text)
        time_text = show_match.group(1) if show_match else (range_match.group(1) if range_match else None)
        if not time_text:
            return None

        start_at = parse_datetime(f"{date_match.group(0)} {time_text}")
        if start_at is None:
            return None

        title = None
        for tag in soup.find_all(["h1", "h2"]):
            value = clean(tag.get_text(" ", strip=True))
            if value and value.casefold() not in {"the rabbit box"}:
                title = value
                break
        if not title:
            return None

        slug = urlparse(event_url).path.rstrip("/").split("/")[-1]
        source_event_id = slug or stable_source_id(cls.key, event_url, title)

        doors = DOORS_RE.search(text)
        age = AGE_RE.search(text)

        ticket_url = None
        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            if any(host in href for host in (
                "tickets.venuepilot.com",
                "tickets.thetripledoor.net",
                "eventbrite.com",
                "app.opendate.io",
                "ticketweb.com",
            )):
                ticket_url = href
                break

        return Event(
            id=f"{cls.key}:{source_event_id}",
            source=cls.key,
            source_event_id=source_event_id,
            title=title,
            venue=cls.venue,
            start_at=start_at.astimezone(TZ),
            event_url=event_url,
            ticket_url=ticket_url,
            doors_time=clean(doors.group(1)).upper() if doors else None,
            age_restriction=clean(age.group(1)) if age else None,
            status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
            sold_out="sold out" in lower,
            metadata={"platform": "squarespace_events"},
        )
