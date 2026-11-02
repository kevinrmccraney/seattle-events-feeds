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
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+\d{4}\b",
    re.I,
)
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[ap]m)\b", re.I)
AGE_RE = re.compile(r"\b(All Ages|\d{2}\+|\d{1,2}\+)\b", re.I)
OPENDATE_RE = re.compile(r"app\.opendate\.io/e/", re.I)
EVENT_ID_RE = re.compile(r"-(\d+)(?:[/?#].*)?$")


class ElCorazonCalendarSource(EventSource):
    base_url = "https://www.elcorazonseattle.com"
    calendar_url = "https://www.elcorazonseattle.com/calendar"

    def __init__(self, key: str, name: str, venue: str):
        self.key = key
        self.name = name
        self.venue = venue

    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
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

        # Event cards contain Opendate links for ticketing/details. Use those as
        # stable anchors and route by the exact physical venue text.
        for anchor in soup.find_all("a", href=True):
            href = urljoin(self.base_url, anchor.get("href", ""))
            if not OPENDATE_RE.search(href):
                continue

            card = self._find_card(anchor)
            if card is None:
                continue
            text = clean(card.get_text(" ", strip=True))
            lines = [clean(v) for v in card.stripped_strings if clean(v)]

            if not any(self._matches_venue(v) for v in lines):
                continue

            dates = DATE_RE.findall(text)
            times = TIME_RE.findall(text)
            if not dates or not times:
                continue

            # Live calendar renders doors then show; use the last visible time.
            start_at = parse_datetime(f"{dates[0]} {times[-1]}")
            if start_at is None:
                continue

            id_match = EVENT_ID_RE.search(href)
            source_event_id = (
                id_match.group(1) if id_match
                else stable_source_id(self.key, href, self._title(card) or "")
            )
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            title = self._title(card)
            if not title:
                continue

            support = self._support(card, title)
            promoter = self._promoter(card, title)
            age_match = AGE_RE.search(text)
            age = clean(age_match.group(1)) if age_match else None

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
                image_url = image.get("src") or image.get("data-src")
                if image_url:
                    image_url = urljoin(self.base_url, image_url)

            events.append(
                Event(
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
                    age_restriction=age,
                    status=status,
                    sold_out="sold out" in lower,
                    metadata={"platform": "opendate", "calendar": "elcorazonseattle.com"},
                )
            )
        return dedupe(events)

    def _matches_venue(self, value: str) -> bool:
        normalized = value.casefold()
        if self.venue == "El Corazón":
            return normalized in {"el corazón", "el corazon"} or normalized.endswith(" - el corazón") or normalized.endswith(" - el corazon")
        return normalized == "the funhouse"

    @staticmethod
    def _find_card(anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(12):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if DATE_RE.search(text) and TIME_RE.search(text):
                best = parent
                links = [
                    a for a in parent.find_all("a", href=True)
                    if OPENDATE_RE.search(urljoin("https://www.elcorazonseattle.com", a.get("href", "")))
                ]
                if len(links) == 1:
                    return parent
            node = parent
        return best

    @staticmethod
    def _title(card: Tag) -> str | None:
        # Prefer heading text nearest the event card; skip generic CTA labels.
        for tag in card.find_all(["h2", "h3", "h4", "h5"]):
            value = clean(tag.get_text(" ", strip=True))
            if not value:
                continue
            lower = value.lower()
            if lower in {"get tickets", "tickets", "image"}:
                continue
            if lower.startswith("supporting talent"):
                continue
            return value
        return None

    @staticmethod
    def _support(card: Tag, title: str) -> str | None:
        strings = [clean(v) for v in card.stripped_strings if clean(v)]
        # Webflow listing often exposes primary artist then support as adjacent
        # lines before the duplicated date.
        for value in strings:
            if value.lower().startswith("supporting talent:"):
                tail = clean(value.split(":", 1)[1])
                if tail:
                    return tail
        for tag in card.find_all(["p", "div", "span", "h4", "h5"]):
            value = clean(tag.get_text(" ", strip=True))
            if value.lower().startswith("with "):
                return clean(value[5:])
        return None

    @staticmethod
    def _promoter(card: Tag, title: str) -> str | None:
        for value in [clean(v) for v in card.stripped_strings if clean(v)]:
            lower = value.lower()
            if " presents" in lower and value != title:
                return value
        return None


def ElCorazonSource() -> ElCorazonCalendarSource:
    return ElCorazonCalendarSource("el-corazon", "El Corazón", "El Corazón")


def FunhouseSource() -> ElCorazonCalendarSource:
    return ElCorazonCalendarSource("funhouse", "The Funhouse", "The Funhouse")
