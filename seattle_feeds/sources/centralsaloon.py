from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from requests import Session
from .base import EventSource, dedupe
from ..models import Event
from ..util import TZ, clean, parse_datetime, stable_source_id

MONTH_RE=re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b",re.I)
DAY_RE=re.compile(r"\b(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",re.I)
TIME_RE=re.compile(r"\b(\d{1,2}:\d{2}\s*[ap]m)\b",re.I)

class CentralSaloonSource(EventSource):
    key="central-saloon"; name="The Central Saloon"; venue="The Central Saloon"
    base_url="https://centralsaloon.com/"; listing_url="https://centralsaloon.com/events/"

    def fetch_events(self,session:Session,start:datetime,end:datetime|None=None)->list[Event]:
        r=session.get(self.listing_url,timeout=30,headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status(); events=self.parse_listing(r.text,start.year)
        return dedupe(e for e in events if e.start_at>=start and (end is None or e.start_at<=end))

    @classmethod
    def parse_listing(cls,html:str,default_year:int|None=None)->list[Event]:
        soup=BeautifulSoup(html,"html.parser"); out=[]; seen=set()
        for heading in soup.find_all(["h2","h3","h4"]):
            title=clean(heading.get_text(" ",strip=True))
            if not title or MONTH_RE.search(title): continue
            block=cls._find_card(heading)
            if block is None: continue
            text=clean(block.get_text(" ",strip=True))
            dm=DAY_RE.search(text); tm=TIME_RE.search(text)
            if not dm or not tm: continue
            year=cls._year_from_context(block) or default_year or datetime.now(TZ).year
            start_at=parse_datetime(f"{dm.group(1)} {dm.group(3)} {year} {tm.group(1)}")
            if start_at is None: continue
            event_url=cls._detail_url(block) or cls.listing_url
            sid=f"{stable_source_id(cls.key,event_url,title)}:{start_at.strftime('%Y%m%dT%H%M')}"
            if sid in seen: continue
            seen.add(sid); lower=text.casefold()
            out.append(Event(
                id=f"{cls.key}:{sid}",source=cls.key,source_event_id=sid,
                title=title,venue=cls.venue,start_at=start_at.astimezone(TZ),
                event_url=event_url,ticket_url=event_url,
                status="cancelled" if "cancelled" in lower or "canceled" in lower else "scheduled",
                sold_out="sold out" in lower,
                metadata={"platform":"central_saloon_events"},
            ))
        return dedupe(out)

    @staticmethod
    def _find_card(heading:Tag)->Tag|None:
        cur=heading; best=None
        for _ in range(10):
            par=cur.parent if cur else None
            if not isinstance(par,Tag):break
            text=clean(par.get_text(" ",strip=True))
            if DAY_RE.search(text) and TIME_RE.search(text):
                best=par
                if len(par.find_all(["h2","h3","h4"]))==1:return par
            cur=par
        return best

    @staticmethod
    def _year_from_context(block:Tag)->int|None:
        prev=block
        for _ in range(12):
            prev=prev.find_previous(["h2","h3","h4","h5"]) if prev else None
            if prev is None:break
            m=MONTH_RE.search(clean(prev.get_text(" ",strip=True)))
            if m:return int(m.group(2))
        return None

    @classmethod
    def _detail_url(cls,block:Tag)->str|None:
        for a in block.find_all("a",href=True):
            if "view detail" in clean(a.get_text(" ",strip=True)).casefold():
                return urljoin(cls.base_url,a.get("href",""))
        return None
