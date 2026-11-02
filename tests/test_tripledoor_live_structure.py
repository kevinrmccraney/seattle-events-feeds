import unittest
from seattle_feeds.sources.tripledoor import TripleDoorSource

FIXTURE = '''
<div class="event">
  <a href="/go/events/6575931?feature_id=923529&occurrence_id=762932118&popup=1">Masters of Hawaiian Music - George Kahumoku, Led Kaapana, Jeff Peterson</a>
  <div>Tuesday, October 6 @ 7:30PM</div>
  <div>Mainstage Theatre, 216 Union Street, Seattle</div>
</div>
<div class="event">
  <a href="/go/events/6627298?feature_id=923529&occurrence_id=768073647&popup=1">Federico Aubele @ The Rabbit Box</a>
  <div>Tuesday, September 29 @ 7:30PM</div>
  <div>The Rabbit Box, 94 Pike St, Seattle, WA</div>
</div>
'''

class TripleDoorLiveTests(unittest.TestCase):
    def test_occurrence_id_and_mainstage_filter(self):
        events = TripleDoorSource.parse_listing(FIXTURE, default_year=2026)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e.source_event_id, "762932118")
        self.assertEqual(e.venue, "The Triple Door")
        self.assertEqual(e.start_at.hour, 19)
        self.assertEqual(e.start_at.minute, 30)
