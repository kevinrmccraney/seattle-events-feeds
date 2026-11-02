import unittest
from seattle_feeds.sources.rabbitbox import RabbitBoxSource

HTML = """
<article class="event-card">
  <h1><a href="/events/blessed-blasphemous">Blessed &amp; Blasphemous</a></h1>
  <ul>
    <li>Sunday, November 1, 2026</li>
    <li>1:30 PM 4:30 PM</li>
    <li>The Rabbit Box Theatre <a href="https://maps.google.com/">(map)</a></li>
    <li><a href="https://www.google.com/calendar/">Google Calendar</a> <a href="/calendar.ics">ICS</a></li>
  </ul>
  <p>21+ Id Required</p>
  <p>Sunday, Nov. 1st // Doors 12:30pm // Show 1:30pm</p>
  <a href="https://tickets.venuepilot.com/e/blessed-blasphemous">Tickets</a>
  <a href="/events/blessed-blasphemous">View Event →</a>
</article>

<article class="event-card">
  <h1><a href="/events/songs-in-c-minor">Songs in C Minor</a></h1>
  <ul>
    <li>Sunday, November 1, 2026</li>
    <li>6:00 PM 9:00 PM</li>
    <li>The Rabbit Box Theatre <a href="https://maps.google.com/">(map)</a></li>
    <li><a href="https://www.google.com/calendar/">Google Calendar</a> <a href="/calendar2.ics">ICS</a></li>
  </ul>
  <p>21+ ID Required</p>
  <p>Sunday, Nov. 1st // Doors 6:30pm // Show 7:00pm</p>
  <a href="https://tickets.venuepilot.com/e/songs-in-c-minor">Tickets</a>
  <a href="/events/songs-in-c-minor">View Event →</a>
</article>
"""

class RabbitBoxV86Tests(unittest.TestCase):
    def test_emits_each_real_event_card(self):
        events = RabbitBoxSource.parse_listing(HTML)
        self.assertEqual(len(events), 2)
        self.assertEqual(
            {e.title for e in events},
            {"Blessed & Blasphemous", "Songs in C Minor"},
        )

    def test_never_uses_map_or_calendar_as_title(self):
        events = RabbitBoxSource.parse_listing(HTML)
        forbidden = {
            "map", "(map)", "google calendar", "ics",
            "view event", "view event →", "tickets",
        }
        for event in events:
            self.assertNotIn(event.title.casefold(), forbidden)

    def test_parses_metadata_per_event(self):
        events = RabbitBoxSource.parse_listing(HTML)
        first = next(e for e in events if e.title == "Blessed & Blasphemous")
        second = next(e for e in events if e.title == "Songs in C Minor")
        self.assertEqual(first.doors_time, "12:30PM")
        self.assertEqual(first.age_restriction, "21+")
        self.assertEqual(first.start_at.hour, 13)
        self.assertEqual(second.start_at.hour, 19)
        self.assertIn("venuepilot.com", second.ticket_url)

if __name__ == "__main__":
    unittest.main()
