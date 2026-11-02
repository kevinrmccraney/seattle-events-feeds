import unittest

from seattle_feeds.sources.clockout import ClockOutSource


FIXTURE = """
<div class="event-card">
  <h3>Clock-Out Lounge Presents: ABYSSINIAN CREOLE Nostalgia for the Future album release</h3>
  <div>with Abyssinian Creole, Ghetto Children, Prometheus Brown</div>
  <div>Fri November 06, 2026 Doors: 08:30 pm</div>
  <a href="https://www.ticketweb.com/event/example-clock-out-lounge-tickets/14376894">Buy Tickets $25.18</a>
</div>
<a href="?twpage=1">Next</a>
"""


class ClockOutTests(unittest.TestCase):
    def test_parse_rendered_calendar(self):
        events = ClockOutSource.parse_html(FIXTURE)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.source_event_id, "14376894")
        self.assertEqual(event.venue, "Clock-Out Lounge")
        self.assertEqual(event.start_at.hour, 20)
        self.assertEqual(event.start_at.minute, 30)
        self.assertEqual(event.doors_time, "08:30 PM")
        self.assertIn("Abyssinian Creole", event.support)
        self.assertEqual(event.metadata["platform"], "ticketweb")

    def test_pagination_detection(self):
        self.assertTrue(ClockOutSource._has_next_page(FIXTURE, 0))
        self.assertFalse(ClockOutSource._has_next_page(FIXTURE, 1))


if __name__ == "__main__":
    unittest.main()
