from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from dateutil.parser import parse as parse_date
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, stable_source_id

AXS_EVENT_ID_RE = re.compile(r"/events/(\d+)(?:/|$)")

DATE_RE = re.compile(
    r"(?P<date>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})"
    r"\s+Show\s+(?P<time>\d{1,2}:\d{2}\s+[AP]M)\s+@\s+(?P<venue>.+)$",
    re.I,
)

# Seattle venues observed on the Showbox Presents calendar. Keep this explicit:
# the same calendar includes Portland and other markets.
SEATTLE_VENUES = {
    "The Showbox",
    "Showbox SoDo",
    "The SoDo Lounge",
    "WAMU Theater",
    "Climate Pledge Arena",
    "McCaw Hall at Seattle Center",
    "Paramount Theatre Seattle",
    "The Paramount Theatre",
    "The Moore Theatre",
    "The Neptune Theatre",
    "Substation",
}


class ShowboxSource(EventSource):
    key = "showbox"
    name = "Showbox Presents"
    url = "https://www.showboxpresents.com/events/all"

    @staticmethod
    def _candidate_container(node: Tag) -> Tag:
        block = node
        for _ in range(7):
            parent = block.parent
            if not isinstance(parent, Tag):
                break
            block = parent
            txt = clean(block.get_text(" ", strip=True))
            if block.find("h3") and block.find("a", href=True) and len(txt) <= 2200:
                return block
        return node

    def parse_html(self, html: str, start: datetime, end: datetime | None = None) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Event] = []

        for text_node in soup.find_all(string=re.compile(r"\bShow\s+\d{1,2}:\d{2}\s+[AP]M\s+@\s+", re.I)):
            text = clean(str(text_node))
            match = DATE_RE.search(text)
            if not match:
                # Sometimes the date/time is split across nested tags. Try the parent.
                if isinstance(text_node.parent, Tag):
                    text = clean(text_node.parent.get_text(" ", strip=True))
                    match = DATE_RE.search(text)
            if not match:
                continue

            venue = clean(match.group("venue"))
            if venue not in SEATTLE_VENUES:
                continue

            dt = parse_date(f"{match.group('date')} {match.group('time')}").replace(tzinfo=TZ)
            if dt < start:
                continue

            block = self._candidate_container(text_node.parent)
            heading = block.find("h3")
            if not heading:
                continue
            title_link = heading.find("a", href=True)
            title = clean(heading.get_text(" ", strip=True))
            if not title:
                continue

            event_url = urljoin(self.url, title_link.get("href")) if title_link else self.url
            ticket = None
            for link in block.find_all("a", href=True):
                label = clean(link.get_text(" ", strip=True)).lower()
                if "ticket" in label or label == "cancelled":
                    ticket = link
                    break

            support = None
            for h4 in block.find_all("h4"):
                value = clean(h4.get_text(" ", strip=True))
                if value.lower().startswith("with "):
                    support = re.sub(r"^with\s+", "", value, flags=re.I)
                    break

            h5_values = [clean(h.get_text(" ", strip=True)) for h in block.find_all("h5")]
            h5_values = [x for x in h5_values if x]
            promoter = h5_values[0] if h5_values else None
            subtitle = h5_values[1] if len(h5_values) > 1 else None

            ticket_url = urljoin(self.url, ticket.get("href")) if ticket else None
            ticket_label = clean(ticket.get_text(" ", strip=True)).lower() if ticket else ""
            status = "cancelled" if "cancel" in ticket_label else "scheduled"
            axs_match = AXS_EVENT_ID_RE.search(ticket_url or "")
            source_event_id = (
                axs_match.group(1)
                if axs_match
                else stable_source_id(self.key, event_url, title)
            )

            metadata = {}
            if subtitle:
                metadata["subtitle"] = subtitle

            out.append(
                Event(
                    id=f"showbox:{source_event_id}",
                    source="showbox",
                    source_event_id=source_event_id,
                    title=title,
                    venue=venue,
                    start_at=dt,
                    event_url=event_url,
                    ticket_url=ticket_url,
                    support=support,
                    promoter=promoter,
                    status=status,
                    metadata=metadata,
                )
            )
        return dedupe(out)

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.url, timeout=30)
        response.raise_for_status()
        return self.parse_html(response.text, start, end)
