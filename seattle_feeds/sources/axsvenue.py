from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


AXS_ROW_RE = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\)\s+"
    r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\("
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\)\s+"
    r"(?P<day>\d{1,2}),\s+(?P<year>20\d{2})\s+-\s+"
    r"(?P<time>\d{1,2}:\d{2}\s+[AP]M)\s+"
    r"(?P<title>.+?)\s+"
    r"(?P<venue>Paramount Theatre Seattle|The Neptune Theatre|The Moore Theatre|Substation),\s+"
    r"Seattle,\s+WA,\s+United States",
    re.I,
)

GENERIC_SKIP = (
    " parking",
    "parking ",
    "premium parking",
    "club access",
    "lounge access",
)


class AXSVenueSource(EventSource):
    base_url = "https://www.axs.com"

    def __init__(self, key: str, name: str, venue: str, venue_id: str, slug: str):
        self.key = key
        self.name = name
        self.venue = venue
        self.venue_id = venue_id
        self.slug = slug
        self.url = f"{self.base_url}/venues/{venue_id}/{slug}"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
            )
        }
        events = []
        seen_ids = set()

        # AXS venue pages expose 10 results at a time with ?page=N.
        for page in range(1, 40):
            url = self.url if page == 1 else f"{self.url}?page={page}"
            r = session.get(url, timeout=30, headers=headers)
            if r.status_code == 404:
                break
            r.raise_for_status()

            batch = self.parse_listing(r.text)
            if not batch:
                # AXS sometimes ignores page=1 but returns first page at bare URL.
                if page == 1:
                    continue
                break

            new_count = 0
            for event in batch:
                if event.source_event_id not in seen_ids:
                    seen_ids.add(event.source_event_id)
                    events.append(event)
                    new_count += 1
            if new_count == 0:
                break

        return dedupe(
            e for e in events
            if e.start_at >= start and (end is None or e.start_at <= end)
        )

    def parse_listing(self, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        text = clean(soup.get_text(" ", strip=True))
        out = []
        seen = set()

        for m in AXS_ROW_RE.finditer(text):
            venue_text = clean(m.group("venue"))
            if venue_text.casefold() != self.venue.casefold():
                continue

            title = clean(m.group("title"))
            lower_title = title.casefold()
            if any(token in lower_title for token in GENERIC_SKIP):
                continue

            start_at = parse_datetime(
                f"{m.group('mon')} {m.group('day')}, {m.group('year')} {m.group('time')}"
            )
            if start_at is None:
                continue

            # Use title+datetime occurrence identity. AXS emits separate occurrence rows.
            sid_base = stable_source_id(self.key, self.url, title)
            sid = f"{sid_base}:{start_at.strftime('%Y%m%dT%H%M')}"
            if sid in seen:
                continue
            seen.add(sid)

            status = "scheduled"
            if "cancelled" in lower_title or "canceled" in lower_title:
                status = "cancelled"
            elif "postponed" in lower_title:
                status = "postponed"
            elif "rescheduled" in lower_title or "new date" in lower_title:
                status = "rescheduled"

            age = None
            age_match = re.search(r"\((\d{1,2}\+)\s+Event\)", title, re.I)
            if age_match:
                age = age_match.group(1)

            out.append(Event(
                id=f"{self.key}:{sid}",
                source=self.key,
                source_event_id=sid,
                title=title,
                venue=self.venue,
                start_at=start_at.astimezone(TZ),
                event_url=self.url,
                ticket_url=self.url,
                age_restriction=age,
                status=status,
                sold_out=False,
                metadata={"platform": "axs_venue_inventory", "venue_id": self.venue_id},
            ))

        return dedupe(out)


def ParamountSource() -> AXSVenueSource:
    return AXSVenueSource(
        "paramount",
        "The Paramount Theatre",
        "Paramount Theatre Seattle",
        "101582",
        "paramount-theatre-seattle-seattle-tickets",
    )


def NeptuneSource() -> AXSVenueSource:
    return AXSVenueSource(
        "neptune",
        "The Neptune Theatre",
        "The Neptune Theatre",
        "102572",
        "the-neptune-theatre-seattle-tickets",
    )


def MooreSource() -> AXSVenueSource:
    return AXSVenueSource(
        "moore",
        "The Moore Theatre",
        "The Moore Theatre",
        "101610",
        "the-moore-theatre-seattle-tickets",
    )


def SubstationSource() -> AXSVenueSource:
    return AXSVenueSource(
        "substation",
        "Substation",
        "Substation",
        "131334",
        "substation-seattle-tickets",
    )
