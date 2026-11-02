from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
DATE_RE = re.compile(rf"\b(?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}}\b", re.I)
SHOW_RE = re.compile(r"\bShow:\s*([0-9]{1,2}:[0-9]{2}\s*[AP]M)\b", re.I)
DOORS_RE = re.compile(r"\bDoors:\s*([0-9]{1,2}:[0-9]{2}\s*[AP]M)\b", re.I)
SUPPORT_RE = re.compile(rf"\bwith\s+(.+?)\s+(?=(?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}}\b)", re.I)
EVENT_ID_RE = re.compile(r"-(\d+)(?:[/?#].*)?$")


class TractorSource(EventSource):
    key = "tractor"
    name = "Tractor Tavern"
    base_url = "https://app.opendate.io"
    listing_url = "https://app.opendate.io/c/tractor-tavern-13?layout=iframe"
    venue = "Tractor Tavern"
    max_pages = 20

    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
        events: list[Event] = []
        seen_ids: set[str] = set()

        for page in range(1, self.max_pages + 1):
            url = self.listing_url if page == 1 else f"{self.listing_url}&page={page}"
            response = session.get(url, timeout=30)
            response.raise_for_status()
            batch = self.parse_listing(response.text)
            new = [event for event in batch if event.id not in seen_ids]

            if not batch:
                break
            if not new:
                break

            for event in new:
                seen_ids.add(event.id)
                if event.start_at < start:
                    continue
                if end is not None and event.start_at > end:
                    continue
                events.append(event)

            # Opendate currently paginates the public iframe. If there is no
            # pagination link to a later page, avoid making one extra request.
            soup = BeautifulSoup(response.text, "html.parser")
            has_next = any(
                clean(a.get_text(" ", strip=True)) in {"→", ">", "Next", "next"}
                for a in soup.find_all("a", href=True)
            )
            if not has_next:
                break

        return dedupe(events)

    @classmethod
    def parse_listing(cls, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "")
            if "/e/" not in href:
                continue

            title = clean(anchor.get_text(" ", strip=True))
            if not title:
                continue

            card = cls._find_card(anchor)
            if card is None:
                continue
            text = clean(card.get_text(" ", strip=True))

            # Tractor's Opendate calendar includes Tractor-promoted shows at
            # Sunset Tavern, Neumos, Conor Byrne, etc. This feed is venue-only.
            if not re.search(r"\bTractor Tavern\s*[•\u2022]\s*Seattle\b", text, re.I):
                continue

            date_match = DATE_RE.search(text)
            show_match = SHOW_RE.search(text)
            if not date_match or not show_match:
                continue

            start_at = parse_datetime(f"{date_match.group(0)} {show_match.group(1)}")
            if start_at is None:
                continue

            event_url = urljoin(cls.base_url, href)
            id_match = EVENT_ID_RE.search(event_url)
            source_event_id = (
                id_match.group(1)
                if id_match
                else stable_source_id(cls.key, event_url, title)
            )

            doors_match = DOORS_RE.search(text)
            support_match = SUPPORT_RE.search(text)
            support = clean(support_match.group(1)) if support_match else None

            lower = text.lower()
            status = "scheduled"
            if "cancelled" in lower or "canceled" in lower:
                status = "cancelled"
            elif "postponed" in lower:
                status = "postponed"
            elif "rescheduled" in lower:
                status = "rescheduled"

            image = card.find("img")
            image_url = None
            if image:
                image_url = image.get("src") or image.get("data-src")
                if image_url:
                    image_url = urljoin(cls.base_url, image_url)

            events.append(
                Event(
                    id=f"{cls.key}:{source_event_id}",
                    source=cls.key,
                    source_event_id=source_event_id,
                    title=title,
                    venue=cls.venue,
                    start_at=start_at.astimezone(TZ),
                    event_url=event_url,
                    ticket_url=event_url,
                    image_url=image_url,
                    support=support,
                    doors_time=doors_match.group(1).upper() if doors_match else None,
                    status=status,
                    sold_out="sold out" in lower,
                    metadata={"platform": "opendate"},
                )
            )

        return dedupe(events)

    @classmethod
    def _find_card(cls, anchor: Tag) -> Tag | None:
        """Find the smallest ancestor that contains one complete listing card."""
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(8):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if DATE_RE.search(text) and SHOW_RE.search(text) and "Seattle" in text:
                best = parent
                # Once the ancestor contains multiple event detail links it is
                # probably the page/list container, not the individual card.
                event_links = [a for a in parent.find_all("a", href=True) if "/e/" in a.get("href", "")]
                if len(event_links) == 1:
                    return parent
            node = parent
        return best
