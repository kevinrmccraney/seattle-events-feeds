from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


FULL_DATE_RE = re.compile(
    r"\b(?P<date>(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2}(?:,\s+\d{4})?)\s*@\s*(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b",
    re.I,
)
OCCURRENCE_RE = re.compile(r"[?&]occurrence_id=(\d+)")
FEATURE_RE = re.compile(r"calendar_feature_(\d+)\.turbo_stream", re.I)


class TripleDoorSource(EventSource):
    key = "triple-door"
    name = "The Triple Door"
    venue = "The Triple Door"
    base_url = "https://www.thetripledoor.net"
    listing_url = "https://www.thetripledoor.net/mainstage-calendar"
    max_pages = 60

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
            )
        }
        response = session.get(self.listing_url, timeout=30, headers=headers)
        response.raise_for_status()
        events = self.parse_detail_list(response.text, default_year=start.year)

        feature_id = self.extract_feature_id(response.text)
        if feature_id:
            for page in range(2, self.max_pages + 1):
                url = (
                    f"{self.base_url}/mainstage-calendar/features/load/"
                    f"calendar_feature_{feature_id}.turbo_stream?calendar_page={page}"
                )
                r = session.get(
                    url,
                    timeout=30,
                    headers={**headers, "Accept": "text/vnd.turbo-stream.html,text/html"},
                )
                if r.status_code == 404:
                    break
                r.raise_for_status()
                batch = self.parse_detail_list(r.text, default_year=start.year)
                if not batch:
                    break
                prior_ids = {e.id for e in events}
                events.extend(batch)
                if {e.id for e in events} == prior_ids:
                    break

        return dedupe(
            e for e in events
            if e.start_at >= start and (end is None or e.start_at <= end)
        )

    @staticmethod
    def extract_feature_id(html: str) -> str | None:
        match = FEATURE_RE.search(html)
        return match.group(1) if match else None

    @classmethod
    def parse_detail_list(cls, html: str, default_year: int | None = None) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()

        for text_node in soup.find_all(string=FULL_DATE_RE):
            block = cls._find_detail_block(text_node.parent)
            if block is None:
                continue

            text = clean(block.get_text(" ", strip=True))
            lower = text.casefold()
            if "the rabbit box" in lower or "mainstage theatre" not in lower:
                continue

            match = FULL_DATE_RE.search(text)
            if not match:
                continue

            date_text = match.group("date")
            if not re.search(r"\b20\d{2}\b", date_text):
                date_text = f"{date_text}, {default_year or datetime.now(TZ).year}"
            start_at = parse_datetime(f"{date_text} {match.group('time')}")
            if start_at is None:
                continue

            event_link = None
            title = None
            for a in block.find_all("a", href=True):
                href = urljoin(cls.base_url, a.get("href", ""))
                label = clean(a.get_text(" ", strip=True))
                if "/go/events/" in href and label:
                    event_link = href
                    title = label
                    break
            if not event_link or not title or title.casefold().startswith("closed for"):
                continue

            occurrence_match = OCCURRENCE_RE.search(event_link)
            source_event_id = (
                occurrence_match.group(1)
                if occurrence_match
                else stable_source_id(cls.key, event_link, title)
            )
            if source_event_id in seen:
                continue
            seen.add(source_event_id)

            ticket_url = None
            for a in block.find_all("a", href=True):
                candidate = urljoin(cls.base_url, a.get("href", ""))
                label = clean(a.get_text(" ", strip=True)).casefold()
                if "get tickets" in label or "tickets.thetripledoor.net" in candidate:
                    ticket_url = candidate
                    break

            events.append(Event(
                id=f"{cls.key}:{source_event_id}",
                source=cls.key,
                source_event_id=source_event_id,
                title=title,
                venue=cls.venue,
                start_at=start_at.astimezone(TZ),
                event_url=event_link,
                ticket_url=ticket_url or event_link,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform": "zoogle_turbo_stream"},
            ))

        return dedupe(events)

    @staticmethod
    def _find_detail_block(node: Tag) -> Tag | None:
        current: Tag | None = node
        best: Tag | None = None
        for _ in range(12):
            parent = current.parent if current else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if FULL_DATE_RE.search(text):
                best = parent
                event_links = [a for a in parent.find_all("a", href=True) if "/go/events/" in a.get("href", "")]
                if len(event_links) == 1:
                    return parent
            current = parent
        return best
