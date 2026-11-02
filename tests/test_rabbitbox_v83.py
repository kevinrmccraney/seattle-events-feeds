import unittest
from seattle_feeds.sources.rabbitbox import RabbitBoxSource

ICS = r"""BEGIN:VCALENDAR
BEGIN:VEVENT
UID:rabbit-1@example
DTSTART;TZID=America/Los_Angeles:20261101T190000
DTEND;TZID=America/Los_Angeles:20261101T210000
SUMMARY:Songs in C Minor
LOCATION:The Rabbit Box Theatre\, 94 Pike Street\, Seattle
DESCRIPTION:21+ ID Required\nDoors 6:30pm // Show 7:00pm\nhttps://tickets.venuepilot.com/e/songs-in-c-minor
URL:https://www.therabbitboxseattle.com/events/songs-in-c-minor
END:VEVENT
BEGIN:VEVENT
UID:rabbit-2@example
DTSTART;TZID=America/Los_Angeles:20261107T193000
SUMMARY:The Triple Door presents Dan Rodriguez
LOCATION:The Rabbit Box Theatre\, Seattle
DESCRIPTION:Doors 6:30pm // Performance 7:30pm\nhttps://tickets.thetripledoor.net/eventperformances.asp?evt=2284
URL:https://www.therabbitboxseattle.com/events/dan-rodriguez
END:VEVENT
END:VCALENDAR
"""

class RabbitBoxV83Tests(unittest.TestCase):
    def test_collection_ics_parses_all_events(self):
        events = RabbitBoxSource.parse_ics(ICS)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].title, "Songs in C Minor")
        self.assertEqual(events[0].doors_time, "6:30PM")
        self.assertEqual(events[0].age_restriction, "21+")
        self.assertIn("venuepilot.com", events[0].ticket_url)

if __name__ == "__main__":
    unittest.main()
