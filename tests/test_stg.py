import unittest
from seattle_feeds.sources.stg import ParamountSource, NeptuneSource, MooreSource

HTML = """
<section class="event">
  <h3><a href="/events/oh-mary/">Oh, Mary!<span>Repeating Event</span></a></h3>
  <div>The Paramount Theatre Nov. 3 to 8, 2026 Various showtimes <a href="https://tickets.example/oh-mary">Get Tickets</a></div>
  <div>Nov. 3 7:30 PM</div>
  <div>The Paramount Theatre 911 Pine St, Seattle, WA 98101</div>
  <a href="/events/oh-mary/">Tickets &amp; Info</a>
</section>

<section class="event">
  <h3><a href="/events/oh-mary/">Oh, Mary!<span>Repeating Event</span></a></h3>
  <div>The Paramount Theatre Nov. 3 to 8, 2026 Various showtimes</div>
  <div>Nov. 7 2:00 PM</div>
  <div>The Paramount Theatre 911 Pine St, Seattle, WA 98101</div>
  <a href="/events/oh-mary/">Tickets &amp; Info</a>
</section>

<section class="event">
  <h3><a href="/events/free-paramount-tour/">Free Paramount Tour<span>Repeating Event</span></a></h3>
  <div>1st Saturday of the month 10am to 12pm</div>
  <div>Nov. 7 10:00 AM - 12:00 PM</div>
  <div>The Paramount Theatre 911 Pine St, Seattle, WA 98101</div>
</section>

<section class="event">
  <h3><a href="/events/prateek-kuhad/">Prateek Kuhad – CANCELED</a></h3>
  <div>CANCELED</div>
  <div>Nov. 24 7:00 PM</div>
  <div>The Moore Theatre 1932 Second Avenue, Seattle, WA 98101</div>
</section>

<section class="event">
  <h3><a href="/events/the-aces/">The Aces (RESCHEDULED)</a></h3>
  <div>RESCHEDULED</div>
  <div>Nov. 3 8:00 PM</div>
  <div>The Neptune Theatre 1303 Northeast 45th Street, Seattle, WA 98105</div>
</section>
"""

class STGTests(unittest.TestCase):
    def test_paramount_emits_each_performance_and_skips_tour(self):
        events = ParamountSource().parse_listing(HTML, default_year=2026)
        self.assertEqual(len(events), 2)
        self.assertEqual({e.start_at.hour for e in events}, {14, 19})
        self.assertTrue(all(e.title == "Oh, Mary!" for e in events))
        self.assertEqual(len({e.source_event_id for e in events}), 2)

    def test_moore_cancelled(self):
        events = MooreSource().parse_listing(HTML, default_year=2026)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].status, "cancelled")

    def test_neptune_rescheduled(self):
        events = NeptuneSource().parse_listing(HTML, default_year=2026)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].status, "rescheduled")

if __name__ == "__main__":
    unittest.main()
