import unittest
from seattle_feeds.sources.tripledoor import TripleDoorSource, RabbitBoxSource

FIXTURE='''
<div class="performance">
  <h3><a href="eventperformances.asp?evt=2201">Murray Hill "Showbiz! The Tour"</a></h3>
  <div>Wednesday, November 4, 2026 7:30 PM</div>
  <div>The Triple Door Seattle, WA Buy Tickets</div>
</div>
<div class="performance">
  <h3><a href="eventperformances.asp?evt=2202">Dan Rodriguez at The Rabbit Box</a></h3>
  <div>Saturday, November 7, 2026 7:30 PM</div>
  <div>The Triple Door Seattle, WA Buy Tickets</div>
</div>
<div class="performance">
  <h3><a href="eventperformances.asp?evt=2203">Davide De Pierro</a></h3>
  <div>Thursday, November 5, 2026 7:30 PM</div>
  <div>The Triple Door Seattle, WA sold out</div>
</div>
'''

class TripleDoorTests(unittest.TestCase):
    def test_mainstage(self):
        events=TripleDoorSource().parse_listing(FIXTURE)
        self.assertEqual(len(events),2)
        self.assertTrue(any(e.sold_out for e in events))
        self.assertTrue(all(e.venue=='The Triple Door' for e in events))

    def test_rabbit_box_routing(self):
        events=RabbitBoxSource().parse_listing(FIXTURE)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0].title,'Dan Rodriguez')
        self.assertEqual(events[0].venue,'The Rabbit Box')
        self.assertTrue(events[0].source_event_id.startswith('2202:'))

if __name__ == '__main__':
    unittest.main()
