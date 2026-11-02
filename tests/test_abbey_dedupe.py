import unittest
from datetime import datetime
from seattle_feeds.models import Event
from seattle_feeds.sources.abbeyarts import FremontAbbeySource
from seattle_feeds.util import TZ

class AbbeyDedupeTests(unittest.TestCase):
    def test_cross_transport_occurrence_dedupe_prefers_richer(self):
        source = FremontAbbeySource()
        dt = datetime(2026,11,9,20,0,tzinfo=TZ)
        a = Event(id="a", source=source.key, source_event_id="a", title="Lila Forde, Zan Fiskum @ FREMONT ABBEY", venue=source.venue, start_at=dt, event_url="https://events.humanitix.com/lila", ticket_url="https://events.humanitix.com/lila")
        b = Event(id="b", source=source.key, source_event_id="b", title="Lila Forde, Zan Fiskum", venue=source.venue, start_at=dt, event_url="https://calendar.google.com/x", description="desc")
        merged = source._dedupe_occurrences([a,b])
        self.assertEqual(len(merged),1)
        self.assertIn("humanitix.com", merged[0].event_url)

if __name__ == '__main__': unittest.main()
