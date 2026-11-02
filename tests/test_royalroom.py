import unittest
from seattle_feeds.sources.royalroom import RoyalRoomSource

FIXTURE = '''
<div class="event-list-item">
  <a href="https://theroyalroomseattle.com/event/the-ancient-robotz-2/">The Ancient Robotz</a>
  <span>Sunday, November 1, 2026 @ 07:30 PM -</span>
</div>
<div class="event-list-item">
  <a href="https://theroyalroomseattle.com/event/closed-for-maintenance/">CLOSED FOR MAINTENANCE</a>
  <span>Wednesday, November 4, 2026 -</span>
</div>
'''

class RoyalRoomTests(unittest.TestCase):
    def test_parses_enclosing_event_container(self):
        events = RoyalRoomSource.parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e.source_event_id, "the-ancient-robotz-2")
        self.assertEqual(e.title, "The Ancient Robotz")
        self.assertEqual(e.start_at.hour, 19)
        self.assertEqual(e.start_at.minute, 30)

if __name__ == "__main__":
    unittest.main()
