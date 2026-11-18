"""Substation listings from the venue's own site.

AXS answers this venue with a Cloudflare challenge. substationseattle.com
publishes the same room with a clock time on each card.
"""

from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, canonical_url, clean, stable_source_id


class SubstationSource(EventSource):
    key = "substation"
    name = "Substation"
    venue = "Substation"
    url = "https://substationseattle.com/"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.url, timeout=30)
        response.raise_for_status()
        events = self.parse_listing(response.text)
        return dedupe(
            event for event in events
            if event.start_at >= start and (end is None or event.start_at <= end)
        )

    @classmethod
    def parse_listing(cls, html: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()
        for card in soup.select("article.event"):
            title_node = card.select_one("h3")
            when = card.select_one("time[datetime]")
            if title_node is None or when is None:
                continue
            title = clean(title_node.get_text(" ", strip=True))
            if not title:
                continue
            try:
                start_at = datetime.fromisoformat(when.get("datetime") or "")
            except ValueError:
                continue
            if start_at.tzinfo is None:
                start_at = start_at.replace(tzinfo=TZ)
            else:
                start_at = start_at.astimezone(TZ)
            link = card.select_one("a[href]")
            event_url = canonical_url(link.get("href") or "", cls.url) if link and link.get("href") else cls.url
            sid = f"{stable_source_id(cls.key, event_url, title)}:{start_at.strftime('%Y%m%dT%H%M')}"
            if sid in seen:
                continue
            seen.add(sid)
            lower = title.casefold()
            status = "scheduled"
            if "cancelled" in lower or "canceled" in lower:
                status = "cancelled"
            elif "postponed" in lower:
                status = "postponed"
            image = card.select_one("img[src]")
            events.append(Event(
                id=f"{cls.key}:{sid}",
                source=cls.key,
                source_event_id=sid,
                title=title,
                venue=cls.venue,
                start_at=start_at,
                event_url=event_url,
                ticket_url=event_url,
                image_url=image.get("src") if image else None,
                status=status,
                metadata={"platform": "substation_site"},
            ))
        return dedupe(events)
