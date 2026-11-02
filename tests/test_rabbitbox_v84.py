import unittest
from seattle_feeds.sources.rabbitbox import RabbitBoxSource

HTML = """
<section>
  <h2><a href="/events/blessed-blasphemous">Blessed &amp; Blasphemous</a></h2>
  <div>Sunday, November 1, 2026</div>
  <div>1:30 PM 4:30 PM</div>
  <div>The Rabbit Box Theatre</div>
  <p>21+ Id Required</p>
  <p>Sunday, Nov. 1st // Doors 12:30pm // Show 1:30pm</p>
  <a href="https://tickets.venuepilot.com/e/blessed-blasphemous">Tickets</a>
</section>
<section>
  <h2><a href="/events/songs-in-c-minor">Songs in C Minor</a></h2>
  <div>Sunday, November 1, 2026</div>
  <div>6:00 PM 9:00 PM</div>
  <div>The Rabbit Box Theatre</div>
  <p>Sunday, Nov. 1st // Doors 6:30pm // Show 7:00pm</p>
</section>
"""

class RabbitBoxV84Tests(unittest.TestCase):
    def test_multiple_events(self):
        events = RabbitBoxSource.parse_listing(HTML)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].title, "Blessed & Blasphemous")
        self.assertEqual(events[0].doors_time, "12:30PM")
        self.assertEqual(events[0].age_restriction, "21+")

if __name__ == "__main__":
    unittest.main()
