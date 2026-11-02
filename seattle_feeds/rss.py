from __future__ import annotations

import json
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, register_namespace

from .models import Event

NS = "urn:seattle-events:v1"
register_namespace("seattle", NS)


def _text(parent: Element, tag: str, value) -> None:
    if value is None:
        return
    node = SubElement(parent, tag)
    if isinstance(value, bool):
        node.text = "true" if value else "false"
    else:
        node.text = str(value)


def write_feed(path: str | Path, *, title: str, link: str, source_key: str,
               events: list[Event], generated_at: datetime) -> None:
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    _text(channel, "title", title)
    _text(channel, "link", link)
    _text(channel, "description", f"Normalized upcoming events from {title}")
    _text(channel, "lastBuildDate", format_datetime(generated_at))
    _text(channel, f"{{{NS}}}source", source_key)
    _text(channel, f"{{{NS}}}generated_at", generated_at.isoformat())

    for event in sorted(events, key=lambda e: (e.start_at, e.title.lower())):
        item = SubElement(channel, "item")
        _text(item, "title", event.title)
        _text(item, "link", event.event_url)
        guid = SubElement(item, "guid", {"isPermaLink": "false"})
        guid.text = event.id
        desc = event.description or event.support or f"{event.title} at {event.venue}"
        _text(item, "description", desc)

        fields = {
            "source": event.source,
            "source_event_id": event.source_event_id,
            "venue": event.venue,
            "start_at": event.start_at.isoformat(),
            "end_at": event.end_at.isoformat() if event.end_at else None,
            "event_url": event.event_url,
            "ticket_url": event.ticket_url,
            "image_url": event.image_url,
            "support": event.support,
            "promoter": event.promoter,
            "doors_time": event.doors_time,
            "age_restriction": event.age_restriction,
            "status": event.status,
            "sold_out": event.sold_out,
            "metadata": json.dumps(event.metadata, separators=(",", ":"), sort_keys=True),
        }
        for key, value in fields.items():
            _text(item, f"{{{NS}}}{key}", value)

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ElementTree(rss).write(target, encoding="utf-8", xml_declaration=True)
