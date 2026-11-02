from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from requests import Session
from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

DATE_RE = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(?P<day>\d{1,2}),\s+(?P<year>20\d{2})\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M)\b", re.I)

class SubstationSource(EventSource):
    key="substation"; name="Substation"; venue="Substation"
    base_url="https://substationseattle.com/"; listing_url=base_url

    def fetch_events(self, session: Session, start: datetime, end: datetime | None = None) -> list[Event]:
        r=session.get(self.listing_url, timeout=30, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        events=self.parse_listing(r.text)
        return dedupe(e for e in events if e.start_at >= start and (end is None or e.start_at <= end))

    @classmethod
    def parse_listing(cls, html: str) -> list[Event]:
        soup=BeautifulSoup(html,"html.parser"); out=[]; seen=set()
        for node in soup.find_all(string=DATE_RE):
            block=cls._find_card(node.parent)
            if block is None: continue
            text=clean(block.get_text(" ", strip=True)); dm=DATE_RE.search(text)
            if not dm: continue
            start_at=parse_datetime(dm.group(0))
            if start_at is None: continue
            title=cls._title(block)
            if not title: continue
            event_url=cls._event_url(block) or cls.listing_url
            ticket_url=cls._ticket_url(block)
            sid=f"{stable_source_id(cls.key,event_url,title)}:{start_at.strftime('%Y%m%dT%H%M')}"
            if sid in seen: continue
            seen.add(sid)
            description=cls._description(block)
            category=cls._category(block)
            lower=text.casefold()
            out.append(Event(
                id=f"{cls.key}:{sid}", source=cls.key, source_event_id=sid,
                title=title, venue=cls.venue, start_at=start_at.astimezone(TZ),
                event_url=event_url, ticket_url=ticket_url, description=description,
                support=cls._support(description),
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform":"substation_site","category":category},
            ))
        return dedupe(out)

    @staticmethod
    def _find_card(node: Tag) -> Tag | None:
        cur=node; best=None
        for _ in range(12):
            par=cur.parent if cur else None
            if not isinstance(par,Tag): break
            text=clean(par.get_text(" ",strip=True))
            if DATE_RE.search(text) and par.find(["h2","h3","h4"]):
                best=par
                if len(DATE_RE.findall(text))==1: return par
            cur=par
        return best

    @staticmethod
    def _title(block: Tag) -> str | None:
        for tag in block.find_all(["h2","h3","h4"]):
            v=clean(tag.get_text(" ",strip=True))
            if v: return v
        return None

    @classmethod
    def _event_url(cls,block:Tag)->str|None:
        for h in block.find_all(["h2","h3","h4"]):
            a=h.find("a",href=True)
            if a: return urljoin(cls.base_url,a.get("href",""))
        return None

    @classmethod
    def _ticket_url(cls,block:Tag)->str|None:
        for a in block.find_all("a",href=True):
            label=clean(a.get_text(" ",strip=True)).casefold()
            if "get tickets" in label or "buy tickets" in label or label=="tickets":
                return urljoin(cls.base_url,a.get("href",""))
        return None

    @staticmethod
    def _description(block:Tag)->str|None:
        vals=[]
        for p in block.find_all("p"):
            v=clean(p.get_text(" ",strip=True))
            if len(v)>=20: vals.append(v)
        return min(vals,key=len) if vals else None

    @staticmethod
    def _category(block:Tag)->str|None:
        text=clean(block.get_text(" ",strip=True))
        for c in ("EDM / Electronic","Indie","Rock","Metal","Hip-Hop","Hip Hop","Punk","Pop","Jazz","Comedy"):
            if c.casefold() in text.casefold(): return c
        return None

    @staticmethod
    def _support(description:str|None)->str|None:
        if not description:return None
        m=re.search(r"\bwith support from\s+(.+?)(?:\.|$)",description,re.I)
        return clean(m.group(1)) if m else None
