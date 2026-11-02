import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from seattle_feeds.models import Event
from seattle_feeds.rss import NS, write_feed
from seattle_feeds.util import TZ


class RssTests(unittest.TestCase):
    def test_round_trip_fields_present(self):
        event = Event(
            id="x:1", source="x", source_event_id="1", title="Band", venue="Venue",
            start_at=datetime(2026, 11, 10, 20, 0, tzinfo=TZ), event_url="https://example.com/e",
            ticket_url="https://example.com/t", support="Support", sold_out=True,
            metadata={"artists": ["Band", "Support"]},
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.xml"
            write_feed(p, title="X", link="https://example.com", source_key="x", events=[event], generated_at=datetime(2026,11,1,tzinfo=TZ))
            root = ET.parse(p).getroot()
            item = root.find("./channel/item")
            self.assertEqual(item.findtext("guid"), "x:1")
            self.assertEqual(item.findtext(f"{{{NS}}}source_event_id"), "1")
            self.assertEqual(item.findtext(f"{{{NS}}}sold_out"), "true")


if __name__ == "__main__":
    unittest.main()
