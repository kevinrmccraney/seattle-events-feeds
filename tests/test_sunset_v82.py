
import unittest
from seattle_feeds.sources.crocodile import SunsetTavernSource

FIXTURE = """
<div><a href="https://link.dice.fm/a">GEORGIA PARKER Nov 2, 2026 8:00 PM Sunset Tavern Buy Tickets</a></div>
<div><a href="https://www.ticketweb.com/b">JON SPENCER Nov 9, 2026 8:00 PM Sunset Tavern Buy Tickets</a></div>
<div><a href="https://link.dice.fm/c">ALEX CAMERON Nov 11, 2026 8:00 PM Sunset Tavern Buy Tickets</a></div>
<div><a href="https://link.dice.fm/d">HARBOUR Dec 5, 2026 9:00 PM Sunset Tavern Buy Tickets</a></div>
"""

class SunsetV82Tests(unittest.TestCase):
    def test_parses_all_matching_events(self):
        events = SunsetTavernSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events), 4)

if __name__ == "__main__":
    unittest.main()
