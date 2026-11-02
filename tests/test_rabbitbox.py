import unittest
from seattle_feeds.sources.rabbitbox import RabbitBoxSource

FIXTURE = '''
<article>
  <h1><a href="/events/the-triple-door-presents-dan-rodriguez">The Triple Door presents Dan Rodriguez</a></h1>
  <div>Saturday, November 7, 2026</div>
  <div>7:30 PM 9:30 PM</div>
  <div>The Rabbit Box Theatre</div>
  <p>Saturday, November 7th // Doors 6:30pm // Performance 7:30pm</p>
  <a href="https://tickets.thetripledoor.net/eventperformances.asp?evt=2284">Tickets</a>
</article>
'''

class RabbitBoxTests(unittest.TestCase):
    def test_first_party_event(self):
        events = RabbitBoxSource.parse_listing(FIXTURE)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e.source_event_id, "the-triple-door-presents-dan-rodriguez")
        self.assertEqual(e.start_at.hour, 19)
        self.assertEqual(e.doors_time, "6:30PM")
        self.assertIn("thetripledoor.net", e.ticket_url)
