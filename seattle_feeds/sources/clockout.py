from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


class ClockOutSource(EventSource):
    key = "clockout"
    name = "Clock-Out Lounge"
    url = "https://clockoutlounge.com/?post_type=tribe_events&ical=1&eventDisplay=list"
    venue = "Clock-Out Lounge"

    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
        response = session.get(self.url, timeout=30)
        response.raise_for_status()
        events = self.parse_ics(response.text)
        return [
            event
            for event in events
            if event.start_at >= start and (end is None or event.start_at <= end)
        ]

    @classmethod
    def parse_ics(cls, text: str) -> list[Event]:
        events: list[Event] = []
        for raw in cls._vevents(text):
            props = cls._properties(raw)
            title = clean(cls._first(props, "SUMMARY"))
            if not title:
                continue

            start_value, start_params = cls._first_with_params(props, "DTSTART")
            start_at = cls._parse_ics_datetime(start_value, start_params)
            if start_at is None:
                continue

            end_value, end_params = cls._first_with_params(props, "DTEND")
            end_at = cls._parse_ics_datetime(end_value, end_params) if end_value else None

            uid = clean(cls._first(props, "UID"))
            event_url = clean(cls._first(props, "URL"))
            description = cls._unescape(cls._first(props, "DESCRIPTION")).strip() or None
            location = clean(cls._unescape(cls._first(props, "LOCATION")))

            source_event_id = uid or stable_source_id(cls.key, event_url, title)
            # UIDs sometimes contain domains and punctuation; they are valid IDs,
            # but keep the normalized row identifier compact and deterministic.
            row_id = stable_source_id(cls.key, source_event_id, title)

            lower = f"{title} {description or ''}".lower()
            status_raw = clean(cls._first(props, "STATUS")).lower()
            status = "scheduled"
            if status_raw == "cancelled" or "cancelled" in lower or "canceled" in lower:
                status = "cancelled"
            elif "postponed" in lower:
                status = "postponed"
            elif "rescheduled" in lower:
                status = "rescheduled"

            doors = None
            if description:
                match = re.search(r"\bdoors(?:\s+open)?\s*[:\-]?\s*([0-9]{1,2}(?::[0-9]{2})?\s*[ap]m)\b", description, re.I)
                if match:
                    doors = match.group(1).upper()

            age = None
            if description:
                match = re.search(r"(\ball\s+ages\b|\b\d{2}\+)", description, re.I)
                if match:
                    age = clean(match.group(1))

            support = None
            if description:
                match = re.search(r"\bwith\s+([^\\\n.;]+)", description, re.I)
                if match:
                    support = clean(match.group(1))

            ticket_url = event_url or None
            events.append(
                Event(
                    id=f"{cls.key}:{row_id}",
                    source=cls.key,
                    source_event_id=source_event_id,
                    title=title,
                    venue=cls.venue,
                    start_at=start_at,
                    end_at=end_at,
                    event_url=event_url or cls.url,
                    ticket_url=ticket_url,
                    description=description,
                    support=support,
                    doors_time=doors,
                    age_restriction=age,
                    status=status,
                    sold_out="sold out" in lower,
                    metadata={
                        "platform": "tribe_ics",
                        "location": location or None,
                    },
                )
            )

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

        # DATE-only values are interpreted at local midnight.
        if params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", value):
            try:
                d = datetime.strptime(value[:8], "%Y%m%d")
                return d.replace(tzinfo=TZ)
            except ValueError:
                return None

        if value.endswith("Z"):
            try:
                return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(TZ)
            except ValueError:
                pass

        for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.replace(tzinfo=TZ)
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
