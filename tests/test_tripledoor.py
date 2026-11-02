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

class TripleDoorTests(unittest.TestCase):
    def test_mainstage_occurrence(self):
        events = TripleDoorSource.parse_listing(FIXTURE, default_year=2026)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_event_id, '762932118')
        self.assertEqual(events[0].venue, 'The Triple Door')

if __name__ == '__main__':
    unittest.main()
