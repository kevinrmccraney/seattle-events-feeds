import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from seattle_feeds import main
from seattle_feeds.models import Event
from seattle_feeds.util import TZ

class FakeSource:
    key = "rabbit-box"
    name = "Rabbit Box"
    allow_empty = False
    def fetch_events(self, session, start, end=None):
        return [Event(
            id=f"rabbit-box:{i}", source="rabbit-box", source_event_id=str(i),
            title=f"Event {i}", venue="The Rabbit Box",
            start_at=datetime(2026, 11, 10+i, 20, 0, tzinfo=TZ),
            event_url=f"https://example.com/{i}") for i in range(3)]

class InventoryGuardTests(unittest.TestCase):
    def test_below_minimum_preserves_last_good_feed(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / "feeds").mkdir(parents=True)
            old = out / "feeds" / "rabbit-box.xml"
            old.write_text("LAST GOOD")
            with patch.object(main, "SOURCES", [FakeSource()]):
                failures = main.generate(td)
            self.assertEqual(failures, 1)
            self.assertEqual(old.read_text(), "LAST GOOD")
            status = json.loads((out / "status" / "rabbit-box.json").read_text())
            self.assertEqual(status["code"], "inventory_below_expected")
            self.assertFalse(status["success"])

if __name__ == '__main__': unittest.main()
