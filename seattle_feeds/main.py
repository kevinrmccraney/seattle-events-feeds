from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import requests

from .rss import write_feed
from .sources import SOURCES
from .util import TZ


class InventoryBelowExpected(ValueError):
    pass


INVENTORY_MINIMUMS = {
    "paramount": 50,
    "neptune": 50,
    "moore": 25,
    "substation": 25,
    "chop-suey": 10,
    "triple-door": 8,
    "rabbit-box": 15,
    "fremont-abbey": 5,
    "ballard-homestead": 3,
}

SOURCE_LINKS = {
    "neumos": "https://www.neumos.com/events",
    "barboza": "https://www.thebarboza.com/events",
    "vera": "https://theveraproject.org/events/",
    "showbox": "https://calendar.thecrocodile.com/",
    "tractor": "https://tractortavern.com/calendar/",
    "clockout": "https://clockoutlounge.com/",
    "nectar": "https://nectarlounge.com/events/calendar/",
    "hidden-hall": "https://nectarlounge.com/events/calendar/",
    "el-corazon": "https://www.elcorazonseattle.com/calendar",
    "funhouse": "https://www.elcorazonseattle.com/calendar",
    "jazz-alley": "https://www.jazzalley.com/www-home/calendar.jsp",
    "royal-room": "https://theroyalroomseattle.com/events/",
    "crocodile": "https://calendar.thecrocodile.com/",
    "sunset-tavern": "https://calendar.thecrocodile.com/",
    "belltown-yacht-club": "https://calendar.thecrocodile.com/",
    "baba-yaga": "https://calendar.thecrocodile.com/",
    "triple-door": "https://www.thetripledoor.net/mainstage-calendar",
    "rabbit-box": "https://www.therabbitboxseattle.com/events",
    "fremont-abbey": "https://www.fremontabbey.org/calendar/",
    "ballard-homestead": "https://www.fremontabbey.org/calendar/",
    "paramount": "https://www.axs.com/venues/101582/paramount-theatre-seattle-seattle-tickets",
    "neptune": "https://www.axs.com/venues/102572/the-neptune-theatre-seattle-tickets",
    "moore": "https://www.axs.com/venues/101610/the-moore-theatre-seattle-tickets",
    "chop-suey": "https://www.ticketweb.com/venue/chop-suey-seattle-wa/19270",
    "substation": "https://www.axs.com/venues/131334/substation-seattle-tickets",
    "central-saloon": "https://centralsaloon.com/events/",
}


def classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if isinstance(exc, PermissionError) and "dice" in msg:
        return "dice_api_auth_failed"
    if isinstance(exc, requests.Timeout):
        return "source_timeout"
    if isinstance(exc, requests.HTTPError):
        return "source_http_error"
    if isinstance(exc, requests.RequestException):
        return "source_request_error"
    if isinstance(exc, InventoryBelowExpected):
        return "inventory_below_expected"
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return "source_parse_error"
    return "source_error"


def generate(output_dir: str = "docs", only: set[str] | None = None) -> int:
    now = datetime.now(TZ)
    session = requests.Session()
    session.headers.update({"User-Agent": "SeattleEventsFeeds/6.0 (+weekly normalized RSS producer)"})
    out = Path(output_dir)
    (out / "feeds").mkdir(parents=True, exist_ok=True)
    (out / "status").mkdir(parents=True, exist_ok=True)
    failures = 0

    for source in SOURCES:
        if only and source.key not in only:
            continue
        status_path = out / "status" / f"{source.key}.json"
        try:
            events = source.fetch_events(session, now, None)
            if not events and not source.allow_empty:
                raise ValueError(f"{source.key}: source returned zero upcoming events")
            minimum = INVENTORY_MINIMUMS.get(source.key)
            if minimum is not None and len(events) < minimum:
                raise InventoryBelowExpected(
                    f"{source.key}: inventory below expected minimum "
                    f"({len(events)} < {minimum}); preserving last good feed"
                )
            feed_path = out / "feeds" / f"{source.key}.xml"
            write_feed(
                feed_path,
                title=source.name,
                link=SOURCE_LINKS.get(source.key, getattr(source, "base_url", getattr(source, "url", ""))),
                source_key=source.key,
                events=events,
                generated_at=now,
            )
            status = {
                "source": source.key,
                "success": True,
                "generated_at": now.isoformat(),
                "event_count": len(events),
                "feed": f"feeds/{source.key}.xml",
            }
            print(f"{source.key}: wrote {len(events)} events")
        except Exception as exc:
            failures += 1
            status = {
                "source": source.key,
                "success": False,
                "generated_at": now.isoformat(),
                "code": classify_error(exc),
                "message": str(exc),
                "exception_type": type(exc).__name__,
            }
            # Deliberately do not overwrite the last good RSS file.
            print(f"ERROR {source.key}: {exc}")
        status_path.write_text(json.dumps(status, indent=2) + "\n")

    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="docs")
    parser.add_argument("--source", action="append", dest="sources")
    parser.add_argument("--fail-on-source-error", action="store_true")
    args = parser.parse_args()
    failures = generate(args.output_dir, set(args.sources or []))
    if failures and args.fail_on_source_error:
        raise SystemExit(f"{failures} source(s) failed")


if __name__ == "__main__":
    main()
