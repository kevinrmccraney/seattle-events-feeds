import unittest
from seattle_feeds.sources.rabbitbox import RabbitBoxSource

HTML = '''
<article>
  <h1><a href="/events/blessed-blasphemous">Blessed &amp; Blasphemous</a></h1>
  <div>Sunday, November 1, 2026</div><div>1:30 PM 4:30 PM</div>
  <div>The Rabbit Box Theatre <a href="https://maps.google.com">(map)</a></div>
  <a href="https://www.google.com/calendar">Google Calendar</a><a href="/x.ics">ICS</a>
  <p>21+ Id Required</p><p>Doors 12:30pm // Show 1:30pm</p>
  <a href="https://tickets.venuepilot.com/e/blessed">Tickets</a>
  <a href="/events/blessed-blasphemous">View Event →</a>
</article>
<article>
  <h1><a href="/events/songs-in-c-minor">Songs in C Minor</a></h1>
  <div>Sunday, November 1, 2026</div><div>6:00 PM 9:00 PM</div>
  <div>The Rabbit Box Theatre <a href="https://maps.google.com">(map)</a></div>
  <a href="/events/songs-in-c-minor">View Event →</a>
</article>
'''

class RabbitBoxSemanticTests(unittest.TestCase):
    def test_real_event_cards(self):
        events = RabbitBoxSource.parse_listing(HTML)
        self.assertEqual(len(events), 2)
        self.assertEqual({e.title for e in events}, {"Blessed & Blasphemous", "Songs in C Minor"})
        first = next(e for e in events if e.title.startswith("Blessed"))
        self.assertEqual(first.doors_time, "12:30PM")
        self.assertEqual(first.age_restriction, "21+")
        self.assertIn("venuepilot", first.ticket_url)

if __name__ == '__main__': unittest.main()
