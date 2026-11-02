from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean

EVENT_ID_RE = re.compile(r"-tickets-(\d+)(?:/|$)")


class CarbonhouseSource(EventSource):
    per_page = 12

    def __init__(self, key: str, name: str, base_url: str, default_venue: str):
        self.key = key
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.default_venue = default_venue

    def _fetch_batch(self, session: Session, offset: int) -> str:
        response = session.get(
            f"{self.base_url}/events/events_ajax/{offset}",
            params={
                "category": 0,
                "venue": 0,
                "team": 0,
                "per_page": self.per_page,
                "came_from_page": "event-list-page",
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.base_url}/events",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, str):
            raise ValueError(f"{self.key}: expected JSON string containing HTML")
        return payload

    def parse_batch(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []

        for item in soup.select(".eventItem"):
            title_link = item.select_one("h3.title a")
            date_node = item.select_one(".date[aria-label]")
            if not title_link or not date_node:
                continue

            event_url = urljoin(self.base_url, title_link.get("href", ""))
            event_id_match = EVENT_ID_RE.search(event_url)
            if not event_id_match:
                continue
            source_event_id = event_id_match.group(1)

            date_text = " ".join(date_node.get("aria-label", "").split())
            try:
                event_day = datetime.strptime(date_text, "%B %d %Y").date()
            except ValueError:
                continue

            doors = item.select_one(".meta .time")
            doors_time = None
            if doors:
                doors_time = clean(doors.get_text(" ", strip=True))
                doors_time = re.sub(r"^Doors:\s*", "", doors_time, flags=re.I)

            # Carbonhouse cards expose doors, not a distinct show time. Store the
            # event at local midnight and keep doors_time separately rather than
            # inventing a performance start time.
            start_at = datetime(event_day.year, event_day.month, event_day.day, tzinfo=TZ)

            ticket = item.select_one("a.tickets")
            tagline = item.select_one("h4.tagline")
            tour = item.select_one(".promotion-text.tour")
            promoter = item.select_one(".info > .promotion-text:not(.tour)") or item.select_one(".promotion-text:not(.tour)")
            age = item.select_one(".meta .age")
            venue_node = item.select_one(".meta .location")
            image = item.select_one(".thumb img")

            cancelled = bool(ticket and ticket.get("data-canceled", "false").lower() == "true")
            ticket_text = clean(ticket.get_text(" ", strip=True)).lower() if ticket else ""
            sold_out = "sold out" in ticket_text
            status = "cancelled" if cancelled else ("sold_out" if sold_out else "scheduled")

            metadata = {}
            if tour:
                metadata["subtitle"] = clean(tour.get_text(" ", strip=True))

            events.append(
                Event(
                    id=f"{self.key}:{source_event_id}",
                    source=self.key,
                    source_event_id=source_event_id,
                    title=clean(title_link.get_text(" ", strip=True)),
                    venue=clean(venue_node.get_text(" ", strip=True)) if venue_node else self.default_venue,
                    start_at=start_at,
                    event_url=event_url,
                    ticket_url=urljoin(self.base_url, ticket.get("href", "")) if ticket else None,
                    image_url=urljoin(self.base_url, image.get("src", "")) if image else None,
                    support=clean(tagline.get_text(" ", strip=True)) if tagline else None,
                    promoter=clean(promoter.get_text(" ", strip=True)) if promoter else None,
                    doors_time=doors_time or None,
                    age_restriction=clean(age.get_text(" ", strip=True)) if age else None,
                    status=status,
                    sold_out=sold_out,
                    metadata=metadata,
                )
            )
        return dedupe(events)

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        results: list[Event] = []
        seen: set[str] = set()
        offset = 0

        while True:
            batch = self.parse_batch(self._fetch_batch(session, offset))
            if not batch:
                break

            for event in batch:
                if event.id in seen:
                    continue
                seen.add(event.id)
                if event.start_at.date() >= start.date():
                    results.append(event)

            # Fetch the complete currently available calendar. The AJAX endpoint
            # is paginated by offset, so continue until it returns a short page.
            if len(batch) < self.per_page:
                break
            offset += self.per_page

        return dedupe(results)
