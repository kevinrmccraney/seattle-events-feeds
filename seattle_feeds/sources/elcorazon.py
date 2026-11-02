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
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+\d{4}\b",
    re.I,
)
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[ap]m)\b", re.I)
AGE_RE = re.compile(r"\b(All Ages|\d{1,2}\+)\b", re.I)
SHOW_PATH_RE = re.compile(r"/shows/", re.I)


class ElCorazonCalendarSource(EventSource):
    base_url = "https://www.elcorazonseattle.com"
    calendar_url = "https://www.elcorazonseattle.com/calendar"

    def __init__(self, key: str, name: str, venue: str):
        self.key = key
        self.name = name
        self.venue = venue

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.calendar_url, timeout=30)
        response.raise_for_status()
        events = self.parse_calendar(response.text)
        return dedupe(
            event for event in events
            if event.start_at >= start and (end is None or event.start_at <= end)
        )

    def parse_calendar(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        # The live calendar links each event to an internal /shows/... page.
        # Opendate is only linked from the detail page, so it is not a reliable
        # calendar-card anchor.
        for anchor in soup.find_all("a", href=True):
            href = urljoin(self.base_url, anchor.get("href", ""))
            if not SHOW_PATH_RE.search(urlparse(href).path):
                continue

            card = self._find_card(anchor)
            if card is None:
                continue

            lines = [clean(v) for v in card.stripped_strings if clean(v)]
            venue_line = next((v for v in lines if self._matches_venue(v)), None)
            if venue_line is None:
                continue

            text = clean(card.get_text(" ", strip=True))
            date_match = DATE_RE.search(text)
            if not date_match:
                continue
            event_tail = text[date_match.start():]
            times = TIME_RE.findall(event_tail)
            if not times:
                continue

            start_at = parse_datetime(f"{date_match.group(0)} {times[-1]}")
            if start_at is None:
                continue

            title, support, promoter = self._extract_title_support_promoter(lines, date_match.group(0))
            if not title:
                title = self._title_from_anchor(anchor)
            if not title:
                continue

            slug = urlparse(href).path.rstrip("/").split("/")[-1]
            source_event_id = slug or stable_source_id(self.key, href, title)
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            age_match = AGE_RE.search(text)
            lower = text.lower()
            status = "scheduled"
            if "cancelled" in lower or "canceled" in lower:
                status = "cancelled"
            elif "postponed" in lower:
                status = "postponed"
            elif "rescheduled" in lower or "show moved" in lower:
                status = "rescheduled"

            image = card.find("img")
            image_url = None
            if image:
                image_url = image.get("src") or image.get("data-src") or image.get("data-lazy-src")
                if image_url:
                    image_url = urljoin(self.base_url, image_url)

            events.append(Event(
                id=f"{self.key}:{source_event_id}",
                source=self.key,
                source_event_id=source_event_id,
                title=title,
                venue=self.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href,
                ticket_url=href,
                image_url=image_url,
                support=support,
                promoter=promoter,
                doors_time=times[0].upper() if len(times) >= 2 else None,
                age_restriction=clean(age_match.group(1)) if age_match else None,
                status=status,
                sold_out="sold out" in lower,
                metadata={"platform": "webflow_opendate", "calendar": "elcorazonseattle.com"},
            ))

        return dedupe(events)

    def _matches_venue(self, value: str) -> bool:
        normalized = value.casefold().strip()
        if self.venue == "El Corazón":
            return normalized in {"el corazón", "el corazon"} or normalized.endswith(" - el corazón") or normalized.endswith(" - el corazon")
        return normalized == "the funhouse"

    @classmethod
    def _find_card(cls, anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(12):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            has_date = bool(DATE_RE.search(text))
            has_time = bool(TIME_RE.search(text))
            has_venue = any(
                clean(v).casefold() in {"the funhouse", "el corazón", "el corazon"}
                or clean(v).casefold().endswith(" - el corazón")
                or clean(v).casefold().endswith(" - el corazon")
                for v in parent.stripped_strings
            )
            if has_date and has_time and has_venue:
                best = parent
                show_links = [a for a in parent.find_all("a", href=True) if SHOW_PATH_RE.search(urlparse(urljoin(cls.base_url, a.get("href", ""))).path)]
                if len(show_links) == 1:
                    return parent
            node = parent
        return best

    @staticmethod
    def _title_from_anchor(anchor: Tag) -> str | None:
        value = clean(anchor.get_text(" ", strip=True))
        if not value:
            return None
        value = re.sub(r"^\w{3}\s+\d{1,2}\s+\d{1,2}:\d{2}\s*[ap]m\s+", "", value, flags=re.I)
        value = re.sub(r"\s*Buy Tickets\s*$", "", value, flags=re.I)
        return clean(value) or None

    @staticmethod
    def _extract_title_support_promoter(lines: list[str], date_text: str) -> tuple[str | None, str | None, str | None]:
        try:
            date_index = next(i for i, v in enumerate(lines) if v == date_text)
        except StopIteration:
            return None, None, None

        candidates = []
        for v in lines[:date_index]:
            lower = v.lower()
            if lower in {"image", "this is some text inside of a div block.", "buy tickets", "get tickets"}:
                continue
            if re.fullmatch(r"\w{3}\s+\d{1,2}", v):
                continue
            candidates.append(v)

        if not candidates:
            return None, None, None

        title = candidates[0]
        promoter = None
        support = None
        rest = candidates[1:]

        if " presents" in title.lower() and len(rest) >= 1:
            promoter = title
            title = rest[0]
            rest = rest[1:]

        # Calendar commonly repeats a headline/artist line before support.
        if rest and rest[0].casefold() == title.casefold():
            rest = rest[1:]
        if rest:
            support = rest[-1]

        return clean(title) or None, clean(support) or None, clean(promoter) or None


def ElCorazonSource() -> ElCorazonCalendarSource:
    return ElCorazonCalendarSource("el-corazon", "El Corazón", "El Corazón")


def FunhouseSource() -> ElCorazonCalendarSource:
    return ElCorazonCalendarSource("funhouse", "The Funhouse", "The Funhouse")
