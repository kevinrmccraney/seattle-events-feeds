from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


CALENDAR_IDS = (
    "d5m5ei6b2l31gre7k0rmutq1e8@group.calendar.google.com",
    "e2avichif01pf6b1im7aa63gh4@group.calendar.google.com",
)
HOST_URL = "https://events.humanitix.com/host/abbey-arts-presents"

HUMANITIX_EVENT_RE = re.compile(r"^https?://events\.humanitix\.com/(?!host/)[^?#]+", re.I)
DATE_RE = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"\d{1,2},\s+\d{1,2}(?::\d{2})?\s*[ap]m",
    re.I,
)
TICKET_RE = re.compile(r"https?://events\.humanitix\.com/[^\s<>]+", re.I)


class AbbeyArtsSource(EventSource):
    def __init__(self, key: str, name: str, venue: str, aliases: tuple[str, ...]):
        self.key = key
        self.name = name
        self.venue = venue
        self.aliases = tuple(a.casefold() for a in aliases)

    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
        events: list[Event] = []

        # Primary: Humanitix host inventory. This host URL is public and does not
        # use the blocked collection URL that previously returned 403.
        try:
            response = session.get(
                HOST_URL,
                timeout=30,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/141.0 Safari/537.36"
                    )
                },
            )
            response.raise_for_status()
            events.extend(self.parse_host(response.text))
        except Exception:
            # Fallback: venue/reference Google calendars.
            for calendar_id in CALENDAR_IDS:
                url = (
                    "https://calendar.google.com/calendar/ical/"
                    f"{quote(calendar_id, safe='')}/public/basic.ics"
                )
                response = session.get(url, timeout=30)
                response.raise_for_status()
                events.extend(self.parse_ics(response.text))

        return dedupe(
            e for e in events
            if e.start_at >= start and (end is None or e.start_at <= end)
        )

    def parse_host(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(HOST_URL, a.get("href", ""))
            if not HUMANITIX_EVENT_RE.match(href):
                continue

            block = self._find_host_block(a)
            if block is None:
                continue

            text = clean(block.get_text(" ", strip=True))
            haystack = text.casefold()
            if not any(alias in haystack for alias in self.aliases):
                continue

            match = DATE_RE.search(text)
            if not match:
                continue

            start_at = parse_datetime(match.group(0))
            if start_at is None:
                continue

            title = clean(a.get_text(" ", strip=True))
            if not title:
                title = self._title(block)
            if not title:
                continue

            slug = urlparse(href).path.strip("/")
            source_event_id = slug or stable_source_id(self.key, href, title)
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            lower = text.casefold()
            events.append(Event(
                id=f"{self.key}:{source_event_id}",
                source=self.key,
                source_event_id=source_event_id,
                title=title,
                venue=self.venue,
                start_at=start_at.astimezone(TZ),
                event_url=href,
                ticket_url=href,
                age_restriction="All Ages" if "all ages" in lower else None,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "humanitix_host"},
            ))

        return dedupe(events)

    def parse_ics(self, text: str) -> list[Event]:
        events: list[Event] = []
        for raw in self._vevents(text):
            props = self._properties(raw)
            title = clean(self._unescape(self._first(props, "SUMMARY")))
            if not title:
                continue
            description = self._unescape(self._first(props, "DESCRIPTION"))
            location = clean(self._unescape(self._first(props, "LOCATION")))
            haystack = f"{title} {location} {description}".casefold()
            if not any(alias in haystack for alias in self.aliases):
                continue

            start_value, start_params = self._first_with_params(props, "DTSTART")
            start_at = self._parse_ics_datetime(start_value, start_params)
            if start_at is None:
                continue

            end_value, end_params = self._first_with_params(props, "DTEND")
            end_at = self._parse_ics_datetime(end_value, end_params) if end_value else None

            uid = clean(self._first(props, "UID"))
            recurrence_id = clean(self._first(props, "RECURRENCE-ID"))
            source_event_id = uid or stable_source_id(self.key, HOST_URL, title)
            if recurrence_id:
                source_event_id = f"{source_event_id}:{recurrence_id}"

            ticket = None
            match = TICKET_RE.search(description or "")
            if match:
                ticket = match.group(0).rstrip(".,;)")

            status_raw = clean(self._first(props, "STATUS")).casefold()
            lower = f"{title} {description}".casefold()
            status = (
                "cancelled"
                if status_raw == "cancelled" or "cancelled" in lower or "canceled" in lower
                else "scheduled"
            )

            events.append(Event(
                id=f"{self.key}:{source_event_id}",
                source=self.key,
                source_event_id=source_event_id,
                title=title,
                venue=self.venue,
                start_at=start_at.astimezone(TZ),
                end_at=end_at.astimezone(TZ) if end_at else None,
                event_url=ticket or HOST_URL,
                ticket_url=ticket,
                description=clean(description) or None,
                age_restriction="All Ages" if "all ages" in lower else None,
                status=status,
                sold_out="sold out" in lower,
                metadata={"platform": "google_calendar_ics", "location": location or None},
            ))

        return dedupe(events)

    @classmethod
    def _find_host_block(cls, anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(12):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if DATE_RE.search(text):
                best = parent
                event_links = [
                    x for x in parent.find_all("a", href=True)
                    if HUMANITIX_EVENT_RE.match(urljoin(HOST_URL, x.get("href", "")))
                ]
                if len(event_links) <= 1:
                    return parent
            node = parent
        return best

    @staticmethod
    def _title(block: Tag) -> str | None:
        for tag in block.find_all(["h1", "h2", "h3", "h4"]):
            value = clean(tag.get_text(" ", strip=True))
            if value:
                return value
        return None

    @staticmethod
    def _unfold(text: str) -> list[str]:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out: list[str] = []
        for line in lines:
            if line.startswith((" ", "\t")) and out:
                out[-1] += line[1:]
            else:
                out.append(line)
        return out

    @classmethod
    def _vevents(cls, text: str) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] | None = None
        for line in cls._unfold(text):
            if line == "BEGIN:VEVENT":
                current = []
            elif line == "END:VEVENT":
                if current is not None:
                    blocks.append(current)
                current = None
            elif current is not None:
                current.append(line)
        return blocks

    @staticmethod
    def _properties(lines: list[str]) -> dict[str, list[tuple[str, dict[str, str]]]]:
        props: dict[str, list[tuple[str, dict[str, str]]]] = {}
        for line in lines:
            if ":" not in line:
                continue
            left, value = line.split(":", 1)
            parts = left.split(";")
            name = parts[0].upper()
            params: dict[str, str] = {}
            for token in parts[1:]:
                if "=" in token:
                    k, v = token.split("=", 1)
                    params[k.upper()] = v
            props.setdefault(name, []).append((value, params))
        return props

    @staticmethod
    def _first(props, name: str) -> str:
        values = props.get(name, [])
        return values[0][0] if values else ""

    @staticmethod
    def _first_with_params(props, name: str) -> tuple[str, dict[str, str]]:
        values = props.get(name, [])
        return values[0] if values else ("", {})

    @staticmethod
    def _parse_ics_datetime(value: str, params: dict[str, str]) -> datetime | None:
        value = clean(value)
        if not value:
            return None
        if params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", value):
            try:
                return datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=TZ)
            except ValueError:
                return None
        if value.endswith("Z"):
            try:
                return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(
                    tzinfo=timezone.utc
                ).astimezone(TZ)
            except ValueError:
                pass
        for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=TZ)
            except ValueError:
                continue
        return parse_datetime(value)

    @staticmethod
    def _unescape(value: str) -> str:
        return (
            value.replace("\\n", "\n")
            .replace("\\N", "\n")
            .replace("\\,", ",")
            .replace("\\;", ";")
            .replace("\\\\", "\\")
        )


def FremontAbbeySource() -> AbbeyArtsSource:
    return AbbeyArtsSource(
        "fremont-abbey",
        "Fremont Abbey Arts Center",
        "Fremont Abbey Arts Center",
        (
            "Fremont Abbey Arts Center",
            "@ Fremont Abbey",
            "Fremont Abbey,",
            "4272 Fremont Ave",
            "4272 Fremont Avenue",
        ),
    )


def BallardHomesteadSource() -> AbbeyArtsSource:
    return AbbeyArtsSource(
        "ballard-homestead",
        "Ballard Homestead",
        "Ballard Homestead",
        (
            "Ballard Homestead",
            "6541 Jones Ave",
            "6541 Jones Avenue",
        ),
    )
