from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from requests import Session
from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

DATE_RE = re.compile(r"\b(?P<dow>Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+(?P<month>\d{1,2})\.(?P<day>\d{1,2})\b", re.I)
DOORS_SHOW_RE = re.compile(r"Doors:\s*(?P<doors>\d{1,2}:\d{2}\s*[AP]M)\s*/\s*Show:\s*(?P<show>\d{1,2}:\d{2}\s*[AP]M)", re.I)
SHOW_RE = re.compile(r"\bShow:\s*(\d{1,2}:\d{2}\s*[AP]M)\b", re.I)

class ChopSueySource(EventSource):
    key = "chop-suey"
    name = "Chop Suey"
    venue = "Chop Suey"
    base_url = "https://chopsuey.com/"
    listing_url = "https://chopsuey.com/"

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        r = session.get(self.listing_url, timeout=30, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        events = self.parse_listing(r.text, start.year)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    @classmethod
    def parse_listing(cls, html: str, default_year: int | None = None) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        out, seen = [], set()
        year = default_year or datetime.now(TZ).year
        for node in soup.find_all(string=DATE_RE):
            block = cls._find_card(node.parent)
            if block is None:
                continue
            text = clean(block.get_text(" ", strip=True))
            dm = DATE_RE.search(text)
            ds = DOORS_SHOW_RE.search(text)
            sm = SHOW_RE.search(text)
            if not dm:
                continue
            show_time = ds.group("show") if ds else (sm.group(1) if sm else None)
            if not show_time:
                continue
            start_at = parse_datetime(f"{dm.group('month')}/{dm.group('day')}/{year} {show_time}")
            if start_at is None:
                continue
            title = cls._title(block, text, dm)
            if not title:
                continue
            event_url = cls._event_url(block) or cls.listing_url
            ticket_url = cls._ticket_url(block)
            sid = f"{stable_source_id(cls.key, event_url, title)}:{start_at.strftime('%Y%m%dT%H%M')}"
            if sid in seen:
                continue
            seen.add(sid)
            lower = text.casefold()
            out.append(Event(
                id=f"{cls.key}:{sid}", source=cls.key, source_event_id=sid,
                title=title, venue=cls.venue, start_at=start_at.astimezone(TZ),
                event_url=event_url, ticket_url=ticket_url,
                doors_time=clean(ds.group("doors")).upper() if ds else None,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform":"chop_suey_site"},
            ))
        return dedupe(out)

    @staticmethod
    def _find_card(node: Tag) -> Tag | None:
        cur, best = node, None
        for _ in range(10):
            par = cur.parent if cur else None
            if not isinstance(par, Tag):
                break
            text = clean(par.get_text(" ", strip=True))
            if DATE_RE.search(text) and ("Show:" in text or DOORS_SHOW_RE.search(text)):
                best = par
                if len(DATE_RE.findall(text)) == 1:
                    return par
            cur = par
        return best

    @classmethod
    def _title(cls, block: Tag, text: str, dm) -> str | None:
        for tag in block.find_all(["h2","h3","h4","h5"]):
            v = clean(tag.get_text(" ", strip=True))
            if v:
                return v
        return clean(text[:dm.start()]) or None

    @classmethod
    def _event_url(cls, block: Tag) -> str | None:
        for a in block.find_all("a", href=True):
            label = clean(a.get_text(" ", strip=True)).casefold()
            if label and "buy tickets" not in label:
                return urljoin(cls.base_url, a.get("href",""))
        return None

    @classmethod
    def _ticket_url(cls, block: Tag) -> str | None:
        for a in block.find_all("a", href=True):
            if "buy tickets" in clean(a.get_text(" ", strip=True)).casefold():
                return urljoin(cls.base_url, a.get("href",""))
        return None
