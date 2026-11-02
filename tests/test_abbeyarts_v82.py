
import unittest
from seattle_feeds.sources.abbeyarts import FremontAbbeySource, BallardHomesteadSource

ICS = r"""BEGIN:VCALENDAR
BEGIN:VEVENT
UID:fremont-1
DTSTART;TZID=America/Los_Angeles:20261105T193000
SUMMARY:Example Fremont Show
LOCATION:4272 Fremont Ave N\, Seattle\, WA 98103
END:VEVENT
BEGIN:VEVENT
UID:ballard-1
DTSTART;TZID=America/Los_Angeles:20261106T193000
SUMMARY:Example Ballard Show
LOCATION:6541 Jones Ave NW\, Seattle\, WA 98117
END:VEVENT
END:VCALENDAR
"""

class AbbeyArtsV82Tests(unittest.TestCase):
    def test_routes_fremont_by_address(self):
        events = FremontAbbeySource().parse_ics(ICS)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_event_id, "fremont-1")

    def test_routes_ballard_by_address(self):
        events = BallardHomesteadSource().parse_ics(ICS)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_event_id, "ballard-1")

if __name__ == "__main__":
    unittest.main()
