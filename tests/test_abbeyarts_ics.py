import unittest
from seattle_feeds.sources.abbeyarts import FremontAbbeySource, BallardHomesteadSource

ICS = r'''BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:abc-fremont
DTSTART;TZID=America/Los_Angeles:20261112T193000
DTEND;TZID=America/Los_Angeles:20261112T220000
SUMMARY:The Round at Fremont Abbey
LOCATION:Fremont Abbey Arts Center\, 4272 Fremont Ave N\, Seattle
DESCRIPTION:All Ages\nTickets: https://events.humanitix.com/the-round-example
STATUS:CONFIRMED
END:VEVENT
BEGIN:VEVENT
UID:abc-ballard
DTSTART;TZID=America/Los_Angeles:20261126T193000
SUMMARY:Bryan John Appleby
LOCATION:Ballard Homestead\, Seattle\, WA
DESCRIPTION:All Ages\nhttps://events.humanitix.com/bryan-john-appleby
END:VEVENT
END:VCALENDAR
'''

class AbbeyArtsICSTests(unittest.TestCase):
    def test_fremont_filter(self):
        events = FremontAbbeySource().parse_ics(ICS)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].venue, "Fremont Abbey Arts Center")
        self.assertEqual(events[0].source_event_id, "abc-fremont")
        self.assertIn("humanitix.com", events[0].ticket_url)

    def test_ballard_filter(self):
        events = BallardHomesteadSource().parse_ics(ICS)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].venue, "Ballard Homestead")
        self.assertEqual(events[0].source_event_id, "abc-ballard")
