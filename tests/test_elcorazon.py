import unittest
from seattle_feeds.sources.elcorazon import ElCorazonSource, FunhouseSource

FIXTURE = '''
<div class="event-card">
  <a href="/shows/fear-factory-cybernetic-domination-tour-2026-20-nov">
    Nov 20 7:00 pm Fear Factory - Cybernetic Domination Tour 2026 Buy Tickets
  </a>
  <div>Fear Factory - Cybernetic Domination Tour 2026</div>
  <div>Fear Factory</div>
  <div>Darkest Hour, Brotality, Lacabra</div>
  <div>November 20, 2026</div>
  <div>November 20, 2026</div>
  <div>This is some text inside of a div block.</div>
  <div>6:00 pm</div><div>7:00 pm</div><div>El Corazón</div>
</div>
<div class="event-card">
  <a href="/shows/gully-boys-my-big-fat-gay-tour-07-nov">
    Nov 07 8:00 pm Gully Boys - My Big Fat Gay Tour Buy Tickets
  </a>
  <div>Gully Boys - My Big Fat Gay Tour</div>
  <div>Gully Boys</div>
  <div>Pollyanna, Black Ends</div>
  <div>November 7, 2026</div><div>November 7, 2026</div>
  <div>7:00 pm</div><div>8:00 pm</div><div>The Funhouse</div>
</div>
'''

class ElCorazonTests(unittest.TestCase):
    def test_routes_el_corazon_from_internal_show_link(self):
        events = ElCorazonSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e.source_event_id, "fear-factory-cybernetic-domination-tour-2026-20-nov")
        self.assertEqual(e.venue, "El Corazón")
        self.assertEqual(e.start_at.hour, 19)
        self.assertEqual(e.doors_time, "6:00 PM")

    def test_routes_funhouse_from_internal_show_link(self):
        events = FunhouseSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e.venue, "The Funhouse")
        self.assertEqual(e.start_at.hour, 20)

if __name__ == "__main__":
    unittest.main()
