import unittest
from seattle_feeds.sources.royalroom import RoyalRoomSource

FIXTURE = """
<div class="tribe-events-calendar-list">
  <a href="https://theroyalroomseattle.com/event/the-ancient-robotz-2/">
    01 Nov The Ancient Robotz Sunday, November 1, 2026 @ 07:30 PM -
  </a>
  <a href="https://theroyalroomseattle.com/event/closed-for-maintenance/">
    04 Nov CLOSED FOR MAINTENANCE Wednesday, November 4, 2026 -
  </a>
</div>
"""

class RoyalRoomTests(unittest.TestCase):
    def test_parse(self):
        events = RoyalRoomSource.parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e.source_event_id, "the-ancient-robotz-2")
        self.assertEqual(e.title, "The Ancient Robotz")
        self.assertEqual(e.start_at.hour, 19)
        self.assertEqual(e.start_at.minute, 30)
