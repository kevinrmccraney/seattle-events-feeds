import hashlib
import json
import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo
from dateutil import parser as dateparser

TZ = ZoneInfo("America/Los_Angeles")


def clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def canonical_url(url: str, base: str) -> str:
    u = urljoin(base, url)
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", ""))


def stable_id(source: str, url: str, title: str, start_at: datetime) -> str:
    identity = f"{source}|{url or title.lower()}|{start_at.date().isoformat()}"
    return hashlib.sha256(identity.encode()).hexdigest()[:32]


def stable_source_id(source: str, url: str, title: str) -> str:
    # Source identity must not depend on mutable fields such as date/time.
    identity = f"{source}|{url or title.lower()}"
    return hashlib.sha256(identity.encode()).hexdigest()[:32]


def json_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def parse_datetime(text: str, default_year: int | None = None) -> datetime | None:
    text = clean(text)
    if not text:
        return None
    default = datetime(default_year or datetime.now(TZ).year, 1, 1, tzinfo=TZ)
    try:
        dt = dateparser.parse(text, fuzzy=True, default=default)
    except (ValueError, OverflowError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)
