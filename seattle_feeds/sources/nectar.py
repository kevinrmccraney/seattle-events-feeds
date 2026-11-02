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
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"\d{1,2}\s+\d{4}\b",
    re.I,
)
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[AP]M)\b", re.I)
AGE_RE = re.compile(r"\b(All Ages|Ages?\s+\d+\+)", re.I)
TIXR_EVENT_RE = re.compile(r"tixr\.com/groups/nectarlounge/events/", re.I)
TIXR_ID_RE = re.compile(r"-(\d+)(?:[/?#].*)?$", re.I)


class NectarCalendarSource(EventSource):
    """Shared Nectar Lounge / Hidden Hall calendar parser.

    Nectar publishes both rooms on one calendar. A source instance filters the
    normalized output to one physical venue so moved/off-site events do not leak
    into either venue feed.
    """

    base_url = "https://nectarlounge.com"
    calendar_url = "https://nectarlounge.com/events/calendar/"

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
            event
            for event in events
            if event.start_at >= start and (end is None or event.start_at <= end)
        )

    def parse_calendar(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen_links: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "")
            absolute = urljoin(self.base_url, href)
            if not TIXR_EVENT_RE.search(absolute):
                continue

            title = clean(anchor.get_text(" ", strip=True))
            if not title or title.upper() in {"TICKETS", "BUY TICKETS", "GET TICKETS"}:
                continue
            if absolute in seen_links:
                continue
            seen_links.add(absolute)

            card = self._find_card(anchor)
            if card is None:
                continue
            text = clean(card.get_text(" ", strip=True))

            # The shared calendar occasionally contains promoted events that
            # have moved to another room (e.g. Neumos). Venue text is the
            # authoritative routing key.
            card_lines = [clean(value) for value in card.stripped_strings if clean(value)]
            if not any(value.lower() == self.venue.lower() for value in card_lines):
                continue

            date_match = DATE_RE.search(text)
            time_match = TIME_RE.search(text)
            if not date_match or not time_match:
                continue

            start_at = parse_datetime(f"{date_match.group(0)} {time_match.group(1)}")
            if start_at is None:
                continue

            id_match = TIXR_ID_RE.search(absolute)
            source_event_id = (
                id_match.group(1)
                if id_match
                else stable_source_id(self.key, absolute, title)
            )

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
                image_url = image.get("src") or image.get("data-src") or image.get("data-lazy-src")
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
                    event_url=absolute,
                    ticket_url=absolute,
                    image_url=image_url,
                    support=support,
                    promoter=promoter,
                    age_restriction=age,
                    status=status,
                    sold_out="sold out" in lower,
                    metadata={"platform": "tixr", "calendar": "nectarlounge.com"},
                )
            )

        return dedupe(events)

    @staticmethod
    def _find_card(anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(10):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if DATE_RE.search(text) and TIME_RE.search(text) and "Seattle" in text:
                best = parent
                title_links = [
                    a for a in parent.find_all("a", href=True)
                    if TIXR_EVENT_RE.search(urljoin("https://nectarlounge.com", a.get("href", "")))
                    and clean(a.get_text(" ", strip=True)).upper() not in {"TICKETS", "BUY TICKETS", "GET TICKETS"}
                ]
                if len(title_links) == 1:
                    return parent
            node = parent
        return best

    @staticmethod
    def _support(card: Tag, title: str) -> str | None:
        # The calendar renders support as a separate heading beginning "with".
        for tag in card.find_all(["h4", "h5", "p", "div", "span"]):
            value = clean(tag.get_text(" ", strip=True))
            if value.lower().startswith("with ") and value != title:
                return clean(value[5:])
        return None

    @staticmethod
    def _promoter(card: Tag, title: str) -> str | None:
        strings = [clean(s) for s in card.stripped_strings if clean(s)]
        try:
            idx = strings.index(title)
        except ValueError:
            return None
        for value in reversed(strings[:idx]):
            if DATE_RE.fullmatch(value):
                continue
            if value.lower().endswith(("present:", "presents:", "present", "presents")):
                return value.rstrip(":")
        return None


def NectarSource() -> NectarCalendarSource:
    return NectarCalendarSource("nectar", "Nectar Lounge", "Nectar Lounge")


def HiddenHallSource() -> NectarCalendarSource:
    return NectarCalendarSource("hidden-hall", "Hidden Hall", "Hidden Hall")
