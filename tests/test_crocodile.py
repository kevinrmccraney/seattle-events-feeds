import unittest
from seattle_feeds.sources.crocodile import CrocodileSource, SunsetTavernSource, BelltownYachtClubSource, BabaYagaSource

FIXTURE = '''
<div class="card">
  <a href="https://www.ticketweb.com/event/foo">BAHAMAS: Industrial Sport & Sound Tour November 3, 2026 The Crocodile Buy Tickets</a>
  <a href="/event/bahamas">BAHAMAS: Industrial Sport & Sound Tour Nov 3, 2026 8:00 PM The Crocodile Buy Tickets</a>
</div>
<div class="card">
  <a href="https://link.dice.fm/foo">GEORGIA PARKER November 2, 2026 Sunset Tavern Buy Tickets</a>
  <a href="/event/georgia-parker">GEORGIA PARKER Nov 2, 2026 8:00 PM Sunset Tavern Buy Tickets</a>
</div>
<div class="card"><a href="/event/jack">JACK BENSINGER Nov 21, 2026 7:30 PM Belltown Yacht Club Buy Tickets</a></div>
<div class="card"><a href="/event/denise">DENISE JULIA Nov 16, 2026 8:00 PM Baba Yaga Buy Tickets</a></div>
<div class="card"><a href="/event/hidden">STOP LIGHT OBSERVATIONS Nov 5, 2026 8:00 PM Hidden Hall Buy Tickets</a></div>
'''

class CrocodileTests(unittest.TestCase):
    def test_routes_crocodile(self):
        events=CrocodileSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0].title,"BAHAMAS: Industrial Sport & Sound Tour")
        self.assertEqual(events[0].venue,"The Crocodile")
        self.assertEqual(events[0].start_at.hour,20)

    def test_routes_other_selected_rooms(self):
        self.assertEqual(len(SunsetTavernSource().parse_calendar(FIXTURE)),1)
        self.assertEqual(len(BelltownYachtClubSource().parse_calendar(FIXTURE)),1)
        self.assertEqual(len(BabaYagaSource().parse_calendar(FIXTURE)),1)

if __name__ == '__main__':
    unittest.main()
