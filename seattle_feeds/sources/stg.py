from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


DATE_RE = re.compile(
    r"\b(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2})\s+(?P<year>20\d{2})\b",
    re.I,
)
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[AP]M)\b", re.I)

SKIP_TITLES = {
    "free paramount tour",
    "free moore tour",
    "free neptune tour",
    "seattle theatre group archive",
}


class STGVenueSource(EventSource):
    base_url = "https://www.stgpresents.org"

    def __init__(self, key: str, name: str, venue: str, category_path: str):
        self.key = key
        self.name = name
        self.venue = venue
        self.url = urljoin(self.base_url, category_path)

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(
            self.url,
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

    def parse_listing(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for heading in soup.find_all(["h3", "h4"]):
            title = clean(heading.get_text(" ", strip=True))
            if not title or title.casefold() in SKIP_TITLES:
                continue

            block = self._nearest_occurrence_container(heading)
            if block is None:
                continue

            text = clean(block.get_text(" ", strip=True))
            if self.venue.casefold() not in text.casefold():
                continue

            date_match = DATE_RE.search(text)
            time_match = TIME_RE.search(text)
            if not date_match or not time_match:
                continue

            start_at = parse_datetime(
                f"{date_match.group('month')} {date_match.group('day')}, "
                f"{date_match.group('year')} {time_match.group(1)}"
            )
            if start_at is None:
                continue

            event_url = self._event_url(block) or self.url
            base_id = stable_source_id(self.key, event_url, title)
            source_event_id = f"{base_id}:{start_at.strftime('%Y%m%dT%H%M')}"
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            lower = text.casefold()
            status = "scheduled"
            if "cancelled" in lower or "canceled" in lower:
                status = "cancelled"
            elif "postponed" in lower:
                status = "postponed"
            elif "rescheduled" in lower:
                status = "rescheduled"

            events.append(Event(
                id=f"{self.key}:{source_event_id}",
                source=self.key,
                source_event_id=source_event_id,
                title=title,
                venue=self.venue,
                start_at=start_at.astimezone(TZ),
                event_url=event_url,
                ticket_url=event_url,
                status=status,
                sold_out="sold out" in lower,
                metadata={"platform": "stg_venue_category"},
            ))

        return dedupe(events)

    def _nearest_occurrence_container(self, heading: Tag) -> Tag | None:
        current: Tag | None = heading
        fallback: Tag | None = None

        for _ in range(10):
            parent = current.parent if current else None
            if not isinstance(parent, Tag):
                break

            text = clean(parent.get_text(" ", strip=True))
            headings = parent.find_all(["h3", "h4"])
            date_count = len(DATE_RE.findall(text))

            if (
                self.venue.casefold() in text.casefold()
                and DATE_RE.search(text)
                and TIME_RE.search(text)
            ):
                fallback = parent

                # Strong boundary: one title + one dated occurrence only.
                if len(headings) == 1 and date_count == 1:
                    return parent

            # Do not climb beyond a semantic event card if it already contains
            # another title/date; that would mix neighboring venue rows.
            if parent.name in {"article", "li"} and (len(headings) > 1 or date_count > 1):
                break

            current = parent

        # Only accept fallback if it still represents exactly one heading/date.
        if fallback is not None:
            ftext = clean(fallback.get_text(" ", strip=True))
            if (
                len(fallback.find_all(["h3", "h4"])) == 1
                and len(DATE_RE.findall(ftext)) == 1
            ):
                return fallback
        return None

    def _event_url(self, block: Tag) -> str | None:
        for a in block.find_all("a", href=True):
            label = clean(a.get_text(" ", strip=True)).casefold()
            href = urljoin(self.base_url, a.get("href", ""))
            if label and label not in {"tickets & info", "get tickets"}:
                return href
        for a in block.find_all("a", href=True):
            return urljoin(self.base_url, a.get("href", ""))
        return None


def ParamountSource() -> STGVenueSource:
    return STGVenueSource(
        "paramount",
        "The Paramount Theatre",
        "The Paramount Theatre",
        "/event-category/paramount/",
    )


def NeptuneSource() -> STGVenueSource:
    return STGVenueSource(
        "neptune",
        "The Neptune Theatre",
        "The Neptune Theatre",
        "/event-category/neptune/",
    )


def MooreSource() -> STGVenueSource:
    return STGVenueSource(
        "moore",
        "The Moore Theatre",
        "The Moore Theatre",
        "/event-category/moore/",
    )
