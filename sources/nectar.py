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
TIXR_RE = re.compile(r"https?://(?:www\.)?tixr\.com/", re.I)
TIXR_ID_RE = re.compile(r"(?:events/[^/?#]*-)?(\d{5,})(?:[/?#].*)?$", re.I)


class NectarCalendarSource(EventSource):
    """Shared Nectar Lounge / Hidden Hall calendar parser.

    The live Nectar calendar uses its own event-page/title markup while ticket
    buttons point to Tixr. Parsing therefore starts from candidate event
    containers and treats the ticket link as metadata, not as the title anchor.
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
        seen_cards: set[int] = set()

        # Candidate anchors include both event-detail links and Tixr ticket links.
        # For each candidate, climb to the smallest ancestor that contains one
        # complete event: date + time + Seattle + an exact venue line.
        for anchor in soup.find_all("a", href=True):
            card = self._find_card(anchor)
            if card is None:
                continue
            ident = id(card)
            if ident in seen_cards:
                continue
            seen_cards.add(ident)

            lines = [clean(v) for v in card.stripped_strings if clean(v)]
            if not any(v.casefold() == self.venue.casefold() for v in lines):
                continue

            text = clean(card.get_text(" ", strip=True))
            date_match = DATE_RE.search(text)
            time_match = TIME_RE.search(text)
            if not date_match or not time_match:
                continue

            start_at = parse_datetime(f"{date_match.group(0)} {time_match.group(1)}")
            if start_at is None:
                continue

            title = self._title(card)
            if not title:
                continue

            event_url = self._event_url(card)
            ticket_url = self._ticket_url(card)
            identity_url = ticket_url or event_url or ""
            id_match = TIXR_ID_RE.search(identity_url)
            source_event_id = (
                id_match.group(1)
                if id_match
                else stable_source_id(self.key, identity_url, title)
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
                    event_url=event_url or ticket_url or self.calendar_url,
                    ticket_url=ticket_url,
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

    def _find_card(self, anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(12):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            lines = [clean(v) for v in parent.stripped_strings if clean(v)]
            has_venue = any(
                v.casefold() in {"nectar lounge", "hidden hall", "neumos"}
                for v in lines
            )
            if DATE_RE.search(text) and TIME_RE.search(text) and "Seattle" in text and has_venue:
                best = parent
                # Prefer the smallest complete card; stop before a container
                # containing multiple distinct dates.
                if len(DATE_RE.findall(text)) == 1:
                    return parent
            node = parent
        return best

    @staticmethod
    def _title(card: Tag) -> str | None:
        # Live calendar renders the main title as a heading. Avoid support text.
        for tag in card.find_all(["h2", "h3", "h4"]):
            value = clean(tag.get_text(" ", strip=True))
            if not value:
                continue
            lower = value.lower()
            if lower.startswith("with "):
                continue
            if value.upper() in {"TICKETS", "BUY TICKETS", "GET TICKETS"}:
                continue
            return value

        # Fallback: first non-ticket link with meaningful text.
        for a in card.find_all("a", href=True):
            value = clean(a.get_text(" ", strip=True))
            if value and value.upper() not in {"TICKETS", "BUY TICKETS", "GET TICKETS"}:
                return value
        return None

    @classmethod
    def _ticket_url(cls, card: Tag) -> str | None:
        for a in card.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            label = clean(a.get_text(" ", strip=True)).lower()
            if TIXR_RE.search(href) or "ticket" in label:
                return href
        return None

    @classmethod
    def _event_url(cls, card: Tag) -> str | None:
        for a in card.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            label = clean(a.get_text(" ", strip=True))
            if not label:
                continue
            if TIXR_RE.search(href):
                continue
            if "ticket" in label.lower():
                continue
            if href.startswith(cls.base_url):
                return href
        return None

    @staticmethod
    def _support(card: Tag, title: str) -> str | None:
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
