import unittest
from seattle_feeds.sources.tripledoor import TripleDoorSource

HTML = """
<a href="/mainstage-calendar/features/load/calendar_feature_906435.turbo_stream?calendar_page=2">Next</a>
<div class="detail">
  <h3><a href="/go/events/6587306?feature_id=923529&occurrence_id=763958799&popup=1">Murray Hill "Showbiz! The Tour"</a></h3>
  <div>Wednesday, November 4 @ 7:30PM Wed, Nov 4 @ 7:30PM</div>
  <div>Mainstage Theatre, 216 Union Street, Seattle</div>
  <a href="https://tickets.thetripledoor.net/example">Get tickets</a>
</div>
<div class="detail">
  <h3><a href="/go/events/6627298?feature_id=923529&occurrence_id=768073647&popup=1">Dan Rodriguez at The Rabbit Box</a></h3>
  <div>Saturday, November 7 @ 7:30PM</div>
  <div>The Rabbit Box, 94 Pike St, Seattle, WA</div>
</div>
"""

class TripleDoorV84Tests(unittest.TestCase):
    def test_feature_id(self):
        self.assertEqual(TripleDoorSource.extract_feature_id(HTML), "906435")

    def test_mainstage_only(self):
        events = TripleDoorSource.parse_detail_list(HTML, default_year=2026)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_event_id, "763958799")

if __name__ == "__main__":
    unittest.main()
