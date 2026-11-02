from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


TICKET_RE = re.compile(
    r"https?://(?:tickets\.venuepilot\.com|tickets\.thetripledoor\.net|"
    r"eventbrite\.com|www\.eventbrite\.com|ticketweb\.com|www\.ticketweb\.com)/[^\s<>]+",
    re.I,
)
DOORS_RE = re.compile(r"\bDoors?\s*[:/\-]?\s*(\d{1,2}(?::\d{2})?\s*[ap]m)\b", re.I)
AGE_RE = re.compile(r"\b(All Ages|\d{1,2}\+)", re.I)


class RabbitBoxSource(EventSource):
    key = "rabbit-box"
    name = "The Rabbit Box"
    venue = "The Rabbit Box"
    feed_url = "https://www.therabbitboxseattle.com/events?format=ical"
    event_base = "https://www.therabbitboxseattle.com/events"

    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
        response = session.get(
            self.feed_url,
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
        events = self.parse_ics(response.text)
        return dedupe(
            e for e in events
            if e.start_at >= start and (end is None or e.start_at <= end)
        )

    @classmethod
    def parse_ics(cls, text: str) -> list[Event]:
        events: list[Event] = []

        for raw in cls._vevents(text):
            props = cls._properties(raw)
            title = clean(cls._unescape(cls._first(props, "SUMMARY")))
            if not title:
                continue

            location = clean(cls._unescape(cls._first(props, "LOCATION")))
            description = cls._unescape(cls._first(props, "DESCRIPTION"))
            lower = f"{title} {location} {description}".casefold()

            # Collection feed is venue-specific, but keep a guard against stray
            # off-site entries.
            if location and "rabbit box" not in location.casefold():
                continue

            start_value, start_params = cls._first_with_params(props, "DTSTART")
            start_at = cls._parse_ics_datetime(start_value, start_params)
            if start_at is None:
                continue

            end_value, end_params = cls._first_with_params(props, "DTEND")
            end_at = cls._parse_ics_datetime(end_value, end_params) if end_value else None

            uid = clean(cls._first(props, "UID"))
            url = clean(cls._first(props, "URL"))
            source_event_id = uid or stable_source_id(cls.key, url or cls.event_base, title)

            ticket_url = None
            match = TICKET_RE.search(description or "")
            if match:
                ticket_url = match.group(0).rstrip(".,;)")

            doors = None
            match = DOORS_RE.search(description or "")
            if match:
                doors = clean(match.group(1)).upper()

            age = None
            match = AGE_RE.search(description or "")
            if match:
                age = clean(match.group(1))

            status_raw = clean(cls._first(props, "STATUS")).casefold()
            status = "scheduled"
            if status_raw == "cancelled" or "cancelled" in lower or "canceled" in lower:
                status = "cancelled"

            events.append(Event(
                id=f"{cls.key}:{source_event_id}",
                source=cls.key,
                source_event_id=source_event_id,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                end_at=end_at.astimezone(TZ) if end_at else None,
                event_url=url or cls.event_base,
                ticket_url=ticket_url,
                description=clean(description) or None,
                doors_time=doors,
                age_restriction=age,
                status=status,
                sold_out="sold out" in lower,
                metadata={"platform": "squarespace_ical", "location": location or None},
            ))

        return dedupe(events)

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
