from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

RANGE_RE = re.compile(
    r"(?P<start>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+[A-Z][a-z]{2}\s+\d{1,2})"
    r"(?:\s*-\s*(?P<end>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+[A-Z][a-z]{2}\s+\d{1,2}))?"
    r",\s*(?P<year>\d{4})",
    re.I,
)
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[ap]m)\b", re.I)
DOORS_RE = re.compile(r"doors?\s+open\s+at\s+(\d{1,2}:\d{2}\s*[ap]m)", re.I)


class JazzAlleySource(EventSource):
    key = "jazz-alley"
    name = "Dimitriou's Jazz Alley"
    venue = "Dimitriou's Jazz Alley"
    base_url = "https://www.jazzalley.com"
    calendar_url = "https://www.jazzalley.com/www-home/calendar.jsp"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.calendar_url, timeout=30)
        response.raise_for_status()
        listings = self.parse_calendar(response.text)
        events: list[Event] = []

        for item in listings:
            detail = {}
            try:
                r = session.get(item["event_url"], timeout=30)
                r.raise_for_status()
                detail = self.parse_detail(r.text)
            except Exception:
                detail = {}

            for performance_at in self.expand_performances(item, detail):
                if performance_at < start:
                    continue
                if end is not None and performance_at > end:
                    continue
                perf_key = performance_at.strftime("%Y%m%dT%H%M")
                source_event_id = f"{item['source_event_id']}:{perf_key}"
                events.append(Event(
                    id=f"{self.key}:{source_event_id}",
                    source=self.key,
                    source_event_id=source_event_id,
                    title=item["title"],
                    venue=self.venue,
                    start_at=performance_at.astimezone(TZ),
                    event_url=item["event_url"],
                    ticket_url=item["event_url"],
                    description=detail.get("description") or item.get("description"),
                    doors_time=detail.get("doors_time"),
                    age_restriction=detail.get("age_restriction") or "All Ages",
                    status="scheduled",
                    sold_out=False,
                    metadata={
                        "platform": "jazzalley",
                        "shownum": item["source_event_id"],
                        "performance_datetime": performance_at.isoformat(),
                    },
                ))
        return dedupe(events)

    @classmethod
    def parse_calendar(cls, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[dict] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, a.get("href", ""))
            if "artist.jsp" not in href or "shownum=" not in href:
                continue
            title = clean(a.get_text(" ", strip=True))
            if not title or title.lower() == "info":
                continue

            context = cls._nearby_context(a)
            match = RANGE_RE.search(context)
            if not match:
                continue

            qs = parse_qs(urlparse(href).query)
            shownum = (qs.get("shownum") or [""])[0] or stable_source_id(cls.key, href, title)
            if shownum in seen:
                continue
            seen.add(shownum)

            year = match.group("year")
            start_date = f"{match.group('start')}, {year}"
            end_date = f"{match.group('end')}, {year}" if match.group("end") else start_date

            results.append({
                "source_event_id": shownum,
                "title": title,
                "start_date": start_date,
                "end_date": end_date,
                "event_url": href,
                "description": cls._description_near_anchor(a, context, year),
            })

        return results

    @classmethod
    def _nearby_context(cls, anchor: Tag) -> str:
        # Prefer the smallest ancestor containing the title and its run dates.
        node: Tag | None = anchor
        for _ in range(10):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if RANGE_RE.search(text):
                return text
            node = parent

        # Fallback: walk forward through nearby siblings/elements until the next
        # distinct Jazz Alley artist link, collecting the adjacent date text.
        parts = [clean(anchor.get_text(" ", strip=True))]
        count = 0
        for element in anchor.next_elements:
            if element is anchor:
                continue
            if isinstance(element, Tag) and element.name == "a":
                href = urljoin(cls.base_url, element.get("href", ""))
                if "artist.jsp" in href and "shownum=" in href and href != urljoin(cls.base_url, anchor.get("href", "")):
                    break
            if isinstance(element, str):
                value = clean(element)
                if value:
                    parts.append(value)
                    count += 1
                    if RANGE_RE.search(" ".join(parts)) or count >= 12:
                        break
        return clean(" ".join(parts))

    @staticmethod
    def _description_near_anchor(anchor: Tag, context: str, year: str) -> str | None:
        if year in context:
            tail = context.split(year, 1)[-1].strip()
            if tail and tail.lower() != "info":
                return tail
        return None

    @staticmethod
    def parse_detail(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        text = clean(soup.get_text(" ", strip=True))
        lower = text.lower()
        doors_match = DOORS_RE.search(text)
        doors_time = doors_match.group(1).upper() if doors_match else None

        description = None
        for p in soup.find_all("p"):
            value = clean(p.get_text(" ", strip=True))
            if len(value) > 80:
                description = value
                break

        times: list[str] = []
        seen: set[str] = set()
        for match in TIME_RE.finditer(text):
            value = clean(match.group(1)).upper()
            if doors_time and value == doors_time:
                continue
            if value not in seen:
                seen.add(value)
                times.append(value)

        return {
            "times": times,
            "doors_time": doors_time,
            "age_restriction": "All Ages" if "all ages" in lower else None,
            "description": description,
        }

    @classmethod
    def expand_performances(cls, item: dict, detail: dict) -> list[datetime]:
        start_day = parse_datetime(item["start_date"])
        end_day = parse_datetime(item["end_date"])
        if start_day is None or end_day is None:
            return []

        days = []
        current = start_day.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        last = end_day.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        while current <= last:
            days.append(current)
            current += timedelta(days=1)

        times = detail.get("times") or ["7:30 PM"]
        performances: list[datetime] = []
        for day in days:
            for time_text in times:
                dt = parse_datetime(f"{day.strftime('%Y-%m-%d')} {time_text}")
                if dt is not None:
                    performances.append(dt.astimezone(TZ))
        return sorted(performances)
