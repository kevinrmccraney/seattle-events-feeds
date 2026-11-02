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
TIME_RANGE_RE = re.compile(
    r"\b(\d{1,2}:\d{2}\s*[AP]M)\s+(\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)
SHOW_RE = re.compile(
    r"\b(?:Show|Showtime|Music|Performance|Music starts at|Trivia|Festivities begin at)\s*[:\-]?\s*"
    r"(\d{1,2}(?::\d{2})?\s*[ap]m)\b",
    re.I,
)
DOORS_RE = re.compile(
    r"\bDoors?\s*[:/\-]?\s*(\d{1,2}(?::\d{2})?\s*[ap]m)\b",
    re.I,
)
AGE_RE = re.compile(r"\b(All Ages|\d{1,2}\+)", re.I)
TICKET_RE = re.compile(
    r"https?://(?:tickets\.venuepilot\.com|tickets\.thetripledoor\.net|"
    r"(?:www\.)?eventbrite\.com|(?:www\.)?ticketweb\.com|app\.opendate\.io)/[^\s<>\"']+",
    re.I,
)

GENERIC_LINK_LABELS = {
    "map",
    "(map)",
    "google calendar",
    "ics",
    "view event",
    "view event →",
    "tickets",
    "buy tickets",
    "directions",
    "calendar",
    "add to calendar",
}


class RabbitBoxSource(EventSource):
    key = "rabbit-box"
    name = "The Rabbit Box"
    venue = "The Rabbit Box"
    listing_url = "https://www.therabbitboxseattle.com/events"

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

        # Squarespace renders each real event with one unique /events/<slug> URL.
        # The same URL may appear on the title and "View Event →". Group by URL
        # first so map/calendar utility links can never become event identities.
        grouped: dict[str, list[Tag]] = {}
        for a in soup.find_all("a", href=True):
            href = urljoin(cls.listing_url, a.get("href", ""))
            path = urlparse(href).path.rstrip("/")
            if not path.startswith("/events/") or path == "/events":
                continue
            grouped.setdefault(href, []).append(a)

        for event_url, anchors in grouped.items():
            title = cls._title_from_event_anchors(anchors)
            if not title:
                continue

            block = cls._find_event_block(anchors)
            if block is None:
                continue

            text = clean(block.get_text(" ", strip=True))
            lower = text.casefold()
            if "the rabbit box theatre" not in lower:
                continue

            date_match = DATE_RE.search(text)
            if not date_match:
                continue

            # Prefer explicit Show/Music/Performance wording in the description.
            # Otherwise use the first time in Squarespace's visible event range.
            show_match = SHOW_RE.search(text)
            range_match = TIME_RANGE_RE.search(text)
            time_text = (
                show_match.group(1)
                if show_match
                else (range_match.group(1) if range_match else None)
            )
            if not time_text:
                continue

            start_at = parse_datetime(f"{date_match.group(0)} {time_text}")
            if start_at is None:
                continue

            slug = urlparse(event_url).path.rstrip("/").split("/")[-1]
            source_event_id = slug or stable_source_id(cls.key, event_url, title)

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
                event_url=event_url,
                ticket_url=ticket_url,
                doors_time=clean(doors.group(1)).upper() if doors else None,
                age_restriction=clean(age.group(1)) if age else None,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "squarespace_events"},
            ))

        return dedupe(events)

    @classmethod
    def _title_from_event_anchors(cls, anchors: list[Tag]) -> str | None:
        candidates: list[str] = []
        for a in anchors:
            value = clean(a.get_text(" ", strip=True))
            if not value:
                continue
            normalized = value.casefold().strip()
            if normalized in GENERIC_LINK_LABELS:
                continue
            if normalized.startswith("view event"):
                continue
            # Exclude utility labels even if Squarespace wraps them oddly.
            if normalized in {"map", "google calendar", "ics"}:
                continue
            candidates.append(value)

        if not candidates:
            return None

        # The event-title anchor is normally the longest meaningful label for
        # this event URL. This also protects against tiny icon/accessibility text.
        return max(candidates, key=len)

    @classmethod
    def _find_event_block(cls, anchors: list[Tag]) -> Tag | None:
        best: Tag | None = None

        # Start from every anchor for this event URL because Squarespace may put
        # the heading link and "View Event" link at different depths.
        for anchor in anchors:
            current: Tag | None = anchor
            for _ in range(14):
                parent = current.parent if current else None
                if not isinstance(parent, Tag):
                    break

                text = clean(parent.get_text(" ", strip=True))
                if DATE_RE.search(text) and "The Rabbit Box Theatre" in text:
                    event_urls = set()
                    for a in parent.find_all("a", href=True):
                        href = urljoin(cls.listing_url, a.get("href", ""))
                        path = urlparse(href).path.rstrip("/")
                        if path.startswith("/events/") and path != "/events":
                            event_urls.add(href)

                    if len(event_urls) == 1:
                        return parent

                    # Keep the smallest plausible block as fallback, but don't
                    # return a container spanning multiple event cards.
                    if best is None:
                        best = parent

                current = parent

        # A multi-event container is unsafe: it can mix one event's title with
        # another event's date. Refuse it rather than emitting corrupted data.
        return None

