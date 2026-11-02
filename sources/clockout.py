from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup, Tag
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id


DATE_RE = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+\d{4}\b",
    re.I,
)
DOORS_RE = re.compile(r"\bDoors:\s*(\d{1,2}:\d{2}\s*[ap]m)\b", re.I)
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[ap]m)\b", re.I)
TICKETWEB_RE = re.compile(r"ticketweb\.com/", re.I)
TICKET_ID_RE = re.compile(r"/(\d{6,})(?:[/?#]|$)")


class ClockOutSource(EventSource):
    key = "clockout"
    name = "Clock-Out Lounge"
    base_url = "https://clockoutlounge.com/"
    venue = "Clock-Out Lounge"

    def fetch_events(
        self,
        session: Session,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Event]:
        events: list[Event] = []
        seen_page_signatures: set[str] = set()

        # The site's public TicketWeb calendar uses ?twpage=N pagination.
        for page in range(0, 30):
            url = f"{self.base_url}?twpage={page}"
            response = session.get(url, timeout=30)
            response.raise_for_status()
            batch = self.parse_html(response.text)

            signature = "|".join(sorted(e.source_event_id for e in batch))
            if not batch:
                break
            if signature in seen_page_signatures:
                break
            seen_page_signatures.add(signature)
            events.extend(batch)

            # Most pages are finite. If there is no obvious next page, stop.
            if not self._has_next_page(response.text, page):
                break

        return dedupe(
            event
            for event in events
            if event.start_at >= start and (end is None or event.start_at <= end)
        )

    @classmethod
    def parse_html(cls, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen_cards: set[int] = set()

        # TicketWeb links are the most reliable per-event anchors on the live page.
        for anchor in soup.find_all("a", href=True):
            href = urljoin(cls.base_url, anchor.get("href", ""))
            if not TICKETWEB_RE.search(href):
                continue

            card = cls._find_card(anchor)
            if card is None:
                continue
            ident = id(card)
            if ident in seen_cards:
                continue
            seen_cards.add(ident)

            text = clean(card.get_text(" ", strip=True))
            date_match = DATE_RE.search(text)
            if not date_match:
                continue

            # Clock-Out often exposes doors but not a separate show time in the
            # listing. When only doors is present, use doors as start_at rather
            # than dropping the event entirely.
            doors_match = DOORS_RE.search(text)
            time_match = doors_match or TIME_RE.search(text)
            time_text = time_match.group(1) if time_match else "12:00 PM"

            start_at = parse_datetime(f"{date_match.group(0)} {time_text}")
            if start_at is None:
                continue

            title = cls._title(card)
            if not title:
                continue

            id_match = TICKET_ID_RE.search(href)
            source_event_id = (
                id_match.group(1)
                if id_match
                else stable_source_id(cls.key, href, title)
            )

            support = cls._support(card, title)
            lower = text.lower()

            status = "scheduled"
            if "cancelled" in lower or "canceled" in lower:
                status = "cancelled"
            elif "postponed" in lower:
                status = "postponed"
            elif "rescheduled" in lower:
                status = "rescheduled"

            price_match = re.search(
                r"\$[\d.]+(?:\s*-\s*\$[\d.]+)?",
                text
            )

            events.append(
                Event(
                    id=f"{cls.key}:{source_event_id}",
                    source=cls.key,
                    source_event_id=source_event_id,
                    title=title,
                    venue=cls.venue,
                    start_at=start_at.astimezone(TZ),
                    event_url=href,
                    ticket_url=href,
                    support=support,
                    doors_time=doors_match.group(1).upper() if doors_match else None,
                    status=status,
                    sold_out="sold out" in lower,
                    metadata={
                        "platform": "ticketweb",
                        "price_text": price_match.group(0) if price_match else None,
                    },
                )
            )

        return dedupe(events)

    @classmethod
    def _find_card(cls, anchor: Tag) -> Tag | None:
        node: Tag | None = anchor
        best: Tag | None = None
        for _ in range(12):
            parent = node.parent if node else None
            if not isinstance(parent, Tag):
                break
            text = clean(parent.get_text(" ", strip=True))
            if DATE_RE.search(text):
                best = parent
                # Stop at the smallest ancestor with one event date and one
                # TicketWeb event link.
                ticket_links = [
                    a for a in parent.find_all("a", href=True)
                    if TICKETWEB_RE.search(urljoin(cls.base_url, a.get("href", "")))
                ]
                if len(DATE_RE.findall(text)) == 1 and len(ticket_links) <= 2:
                    return parent
            node = parent
        return best

    @staticmethod
    def _title(card: Tag) -> str | None:
        # Prefer headings with substantial text.
        for tag in card.find_all(["h1", "h2", "h3", "h4", "h5"]):
            value = clean(tag.get_text(" ", strip=True))
            if not value:
                continue
            lower = value.lower()
            if lower.startswith("with "):
                continue
            if "buy tickets" in lower:
                continue
            return value

        # Fallback: longest non-ticket text link.
        candidates: list[str] = []
        for a in card.find_all("a", href=True):
            value = clean(a.get_text(" ", strip=True))
            if not value:
                continue
            if "ticket" in value.lower():
                continue
            candidates.append(value)
        return max(candidates, key=len) if candidates else None

    @staticmethod
    def _support(card: Tag, title: str) -> str | None:
        for tag in card.find_all(["div", "p", "span", "h4", "h5"]):
            value = clean(tag.get_text(" ", strip=True))
            if value.lower().startswith("with ") and value != title:
                return clean(value[5:])
        return None

    @classmethod
    def _has_next_page(cls, html: str, page: int) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        wanted = page + 1
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            parsed = urlparse(urljoin(cls.base_url, href))
            values = parse_qs(parsed.query).get("twpage", [])
            if any(v.isdigit() and int(v) == wanted for v in values):
                return True
        return False
