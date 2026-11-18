"""STG Presents calendar listings for Paramount, Neptune, and Moore.

The Modern Events Calendar cards usually omit a clock time. Two performances
on the same day can also be identical cards, so each card keeps its own
occurrence index. That index is the order of the cards, not a show time.
When the clock time is missing, the event is stored at local midnight and
doors_time is the indicator "Time not listed".
"""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup
from requests import Session

from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, canonical_url, clean, parse_datetime, stable_source_id


UNLISTED_TIME = "Time not listed"
MAX_PAGES = 20
AJAX_URL = "https://www.stgpresents.org/wp-admin/admin-ajax.php"
LIST_RE = re.compile(r"mecListView\(\s*\{(.*?)\}\s*\)", re.S)


class STGVenueSource(EventSource):
    def __init__(self, key: str, name: str, venue: str, slug: str):
        self.key = key
        self.name = name
        self.venue = venue
        self.slug = slug
        self.url = f"https://www.stgpresents.org/event-category/{slug}/"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        response = session.get(self.url, timeout=30)
        response.raise_for_status()
        cards = self._cards(response.text)
        state = self._list_settings(response.text)
        pages = 1
        while state is not None and pages < MAX_PAGES:
            more = session.post(
                AJAX_URL,
                data=self._payload(state),
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": self.url,
                },
                timeout=30,
            )
            more.raise_for_status()
            body = more.json()
            if not isinstance(body, dict) or not body.get("count"):
                break
            batch = self._cards(body.get("html") or "")
            if not batch:
                break
            cards.extend(batch)
            pages += 1
            if not _has_more(body):
                break
            end_date = body.get("end_date")
            offset = body.get("offset")
            if not end_date or offset is None:
                break
            divider = str(body.get("current_month_divider") or "")
            nxt = (str(end_date), str(offset), divider)
            current = (state["end_date"], state["offset"], state["divider"])
            if nxt == current:
                break
            state = {
                **state,
                "end_date": str(end_date),
                "offset": str(offset),
                "divider": divider,
            }

        return dedupe(
            event for event in self.events_from_cards(cards)
            if _in_window(event, start, end)
        )

    def events_from_cards(self, cards) -> list[Event]:
        counts: dict[tuple[str, str], int] = {}
        events = []
        for card in cards:
            event = self._event_from_card(card, counts)
            if event is not None:
                events.append(event)
        return events

    def _cards(self, html: str):
        return BeautifulSoup(html, "html.parser").select("article.mec-event-article")

    def _list_settings(self, html: str) -> dict[str, str] | None:
        match = LIST_RE.search(html)
        if not match:
            return None
        body = match.group(1)

        def grab(name: str) -> str | None:
            found = re.search(rf'{name}:\s*"([^"]*)"', body)
            return found.group(1) if found else None

        atts = grab("atts") or ""
        category = re.search(r"atts%5Bcategory%5D=(\d+)", atts)
        end_date = grab("end_date")
        offset = grab("offset")
        if not category or not end_date or offset is None:
            return None
        return {
            "end_date": end_date,
            "offset": offset,
            "divider": grab("current_month_divider") or "",
            "category": category.group(1),
        }

    def _payload(self, state: dict[str, str]) -> dict[str, str]:
        return {
            "action": "mec_list_load_more",
            "mec_start_date": state["end_date"],
            "mec_offset": state["offset"],
            "current_month_divider": state["divider"],
            "apply_sf_date": "0",
            "atts[sk-options][list][style]": "classic",
            "atts[category]": state["category"],
            "atts[instance_id]": "mec1",
            "atts[id]": "mec1",
        }

    def _event_from_card(self, card, counts: dict[tuple[str, str], int]) -> Event | None:
        title_link = card.select_one(".mec-event-title a") or card.select_one("a[href]")
        date_node = card.select_one(".mec-start-date-label")
        if title_link is None or date_node is None:
            return None

        place_node = card.select_one(".mec-event-loc-place")
        place = clean(place_node.get_text(" ", strip=True)) if place_node else ""
        if place.casefold() != self.venue.casefold():
            return None

        title = clean(title_link.get_text(" ", strip=True))
        href = title_link.get("href") or ""
        if not title or not href:
            return None

        date_text = clean(date_node.get_text(" ", strip=True))
        parsed_day = parse_datetime(date_text)
        if parsed_day is None:
            return None

        time_node = card.select_one(".mec-event-time")
        time_text = clean(time_node.get_text(" ", strip=True)) if time_node else ""
        event_url = canonical_url(href, self.url)
        image = card.select_one("img[src]")
        image_url = canonical_url(image.get("src") or "", self.url) if image else None
        listed = bool(time_text)
        occurrence = None
        if listed:
            start_at = parse_datetime(f"{date_text} {time_text}")
            if start_at is None:
                return None
            doors_time = None
        else:
            day = parsed_day.astimezone(TZ).date()
            start_at = datetime(day.year, day.month, day.day, tzinfo=TZ)
            doors_time = UNLISTED_TIME
            key = (event_url, day.isoformat())
            counts[key] = counts.get(key, 0) + 1
            occurrence = counts[key]

        lower = title.casefold()
        status = "scheduled"
        if "cancelled" in lower or "canceled" in lower:
            status = "cancelled"
        elif "postponed" in lower:
            status = "postponed"
        elif "rescheduled" in lower or "new date" in lower:
            status = "rescheduled"

        sid_base = stable_source_id(self.key, event_url, title)
        if listed:
            sid = f"{sid_base}:{start_at.strftime('%Y%m%dT%H%M')}"
        else:
            sid = f"{sid_base}:{start_at.strftime('%Y%m%d')}:{occurrence}"

        metadata = {
            "platform": "stg_calendar",
            "show_time_listed": listed,
            "stg_event_id": title_link.get("data-event-id"),
        }
        if occurrence is not None:
            metadata["occurrence_index"] = occurrence

        return Event(
            id=f"{self.key}:{sid}",
            source=self.key,
            source_event_id=sid,
            title=title,
            venue=self.venue,
            start_at=start_at.astimezone(TZ),
            event_url=event_url,
            ticket_url=event_url,
            image_url=image_url,
            doors_time=doors_time,
            status=status,
            metadata=metadata,
        )


def _has_more(body: dict) -> bool:
    value = body.get("has_more_event")
    return value not in (None, False, 0, "0", "")


def _as_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=TZ)
    return value.astimezone(TZ)


def _in_window(event: Event, start: datetime, end: datetime | None) -> bool:
    local_start = _as_local(start)
    if event.metadata.get("show_time_listed") is False:
        if event.start_at.date() < local_start.date():
            return False
    elif event.start_at < local_start:
        return False
    if end is not None and event.start_at > _as_local(end):
        return False
    return True


def ParamountSource() -> STGVenueSource:
    return STGVenueSource(
        "paramount",
        "The Paramount Theatre",
        "The Paramount Theatre",
        "paramount",
    )


def NeptuneSource() -> STGVenueSource:
    return STGVenueSource(
        "neptune",
        "The Neptune Theatre",
        "The Neptune Theatre",
        "neptune",
    )


def MooreSource() -> STGVenueSource:
    return STGVenueSource(
        "moore",
        "The Moore Theatre",
        "The Moore Theatre",
        "moore",
    )
