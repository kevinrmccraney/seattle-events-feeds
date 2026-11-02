
import unittest
from seattle_feeds.sources.rabbitbox import RabbitBoxSource

LISTING = """
<a href="/events/songs-in-c-minor-8fhha">Songs in C Minor</a>
<a href="/events/the-triple-door-presents-dan-rodriguez">The Triple Door presents Dan Rodriguez</a>
"""

DETAIL = """
<html><body>
<h1>Songs in C Minor</h1>
<div>Sunday, November 1, 2026</div>
<div>6:00 PM 9:00 PM</div>
<div>The Rabbit Box Theatre 94 Pike Street Seattle, WA, 98101 United States</div>
<p>21+ ID Required</p>
<p>Sunday, Nov. 1st // Doors 6:30pm // Show 7:00pm</p>
<a href="https://tickets.venuepilot.com/e/songs-in-c-minor-2026-11-01-the-rabbit-box-theatre-seattle-b789a2">Tickets</a>
</body></html>
"""

class RabbitBoxV82Tests(unittest.TestCase):
    def test_extracts_event_links(self):
        links = RabbitBoxSource.extract_event_links(LISTING)
        self.assertEqual(len(links), 2)

    def test_parses_detail(self):
        e = RabbitBoxSource.parse_detail(
            DETAIL,
            "https://www.therabbitboxseattle.com/events/songs-in-c-minor-8fhha",
        )
        self.assertIsNotNone(e)
        self.assertEqual(e.title, "Songs in C Minor")
        self.assertEqual(e.start_at.hour, 19)
        self.assertEqual(e.doors_time, "6:30PM")
        self.assertEqual(e.age_restriction, "21+")

if __name__ == "__main__":
    unittest.main()
