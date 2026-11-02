from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


OCCURRENCE_RE = re.compile(
    r"\b(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
END_TIME_RE = re.compile(
    r"\b(?P<start>\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(?P<end>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)

SKIP_TITLES = {
    "free paramount tour",
    "free moore tour",
    "free neptune tour",
    "seattle theatre group archive",
}


class STGVenueSource(EventSource):
    base_url = "https://www.stgpresents.org"

    def __init__(self, key: str, name: str, venue: str, path: str, address_fragment: str):
        self.key = key
        self.name = name
        self.venue = venue
        self.url = urljoin(self.base_url, path)
        self.address_fragment = address_fragment.casefold()

    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
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
        events = self.parse_listing(response.text, default_year=start.year)
        return dedupe(
            e for e in events
            if e.start_at >= start and (end is None or e.start_at <= end)
        )

    def parse_listing(self, html: str, default_year: int | None = None) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # STG's venue pages render one occurrence row per performance. Anchor on
        # the venue/address text, then climb to the smallest container with a
        # title and an occurrence timestamp.
        for text_node in soup.find_all(string=True):
            raw = clean(str(text_node))
            if self.address_fragment not in raw.casefold():
                continue

            block = self._find_event_block(text_node.parent)
            if block is None:
                continue

            text = clean(block.get_text(" ", strip=True))
            occurrence = OCCURRENCE_RE.search(text)
            if not occurrence:
                continue

            title = self._title(block)
            if not title or title.casefold() in SKIP_TITLES:
                continue

            year_match = YEAR_RE.search(text)
            year = int(year_match.group(1)) if year_match else (default_year or datetime.now(TZ).year)
            start_at = parse_datetime(
                f"{occurrence.group('month')} {occurrence.group('day')}, "
                f"{year} {occurrence.group('time')}"
            )
            if start_at is None:
                continue

            event_url = self._event_url(block) or self.url
            ticket_url = self._ticket_url(block)

            # Same production can have several performances. The STG page exposes
            # each occurrence independently, so datetime is part of occurrence ID.
            base_id = stable_source_id(self.key, event_url, title)
            source_event_id = f"{base_id}:{start_at.strftime('%Y%m%dT%H%M')}"
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            end_at = None
            time_range = END_TIME_RE.search(text)
            if time_range:
                end_at = parse_datetime(
                    f"{occurrence.group('month')} {occurrence.group('day')}, "
                    f"{year} {time_range.group('end')}"
                )

            lower = text.casefold()
            status = "scheduled"
            if "canceled" in lower or "cancelled" in lower:
                status = "cancelled"
            elif "postponed" in lower:
                status = "postponed"
            elif "rescheduled" in lower:
                status = "rescheduled"

            image_url = None
            image = block.find("img")
            if image:
                image_url = (
                    image.get("src")
                    or image.get("data-src")
                    or image.get("data-lazy-src")
                )
                if image_url:
                    image_url = urljoin(self.base_url, image_url)

            events.append(Event(
                id=f"{self.key}:{source_event_id}",
                source=self.key,
                source_event_id=source_event_id,
                title=title,
                venue=self.venue,
                start_at=start_at.astimezone(TZ),
                end_at=end_at.astimezone(TZ) if end_at else None,
                event_url=event_url,
                ticket_url=ticket_url,
                image_url=image_url,
                status=status,
                sold_out="sold out" in lower,
                metadata={"platform": "stg_wordpress_calendar"},
            ))

        return dedupe(events)

    def _find_event_block(self, node: Tag) -> Tag | None:
        current: Tag | None = node
        best: Tag | None = None
        for _ in range(14):
            parent = current.parent if current else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if (
                self.address_fragment in text.casefold()
                and OCCURRENCE_RE.search(text)
                and parent.find(["h2", "h3", "h4"])
            ):
                best = parent

                # Return the smallest block that contains only one physical
                # occurrence for this venue.
                occurrence_count = len(OCCURRENCE_RE.findall(text))
                venue_count = text.casefold().count(self.address_fragment)
                if occurrence_count == 1 and venue_count == 1:
                    return parent
            current = parent
        return best

    @staticmethod
    def _title(block: Tag) -> str | None:
        for tag in block.find_all(["h2", "h3", "h4"]):
            value = clean(tag.get_text(" ", strip=True))
            value = re.sub(r"\s*Repeating Event\s*$", "", value, flags=re.I)
            if value:
                return value
        return None

    def _event_url(self, block: Tag) -> str | None:
        # Heading links usually point to the canonical event detail page.
        for heading in block.find_all(["h2", "h3", "h4"]):
            a = heading.find("a", href=True)
            if a:
                return urljoin(self.base_url, a.get("href", ""))
        for a in block.find_all("a", href=True):
            label = clean(a.get_text(" ", strip=True)).casefold()
            if "tickets & info" in label or "more info" in label:
                return urljoin(self.base_url, a.get("href", ""))
        return None

    def _ticket_url(self, block: Tag) -> str | None:
        # Prefer explicit ticket actions; preserve external ticket provider URL.
        for a in block.find_all("a", href=True):
            label = clean(a.get_text(" ", strip=True)).casefold()
            href = urljoin(self.base_url, a.get("href", ""))
            if (
                "get tickets" in label
                or label == "tickets"
                or "buy tickets" in label
            ):
                return href
        return None


def ParamountSource() -> STGVenueSource:
    return STGVenueSource(
        "paramount",
        "The Paramount Theatre",
        "The Paramount Theatre",
        "/stg-venues/paramount-theatre/events/",
        "911 Pine St",
    )


def NeptuneSource() -> STGVenueSource:
    return STGVenueSource(
        "neptune",
        "The Neptune Theatre",
        "The Neptune Theatre",
        "/stg-venues/neptune-theatre/events/",
        "1303 Northeast 45th Street",
    )


def MooreSource() -> STGVenueSource:
    return STGVenueSource(
        "moore",
        "The Moore Theatre",
        "The Moore Theatre",
        "/stg-venues/moore-theatre/events/",
        "1932 Second Avenue",
    )
