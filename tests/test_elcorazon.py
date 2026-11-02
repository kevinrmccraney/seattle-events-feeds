import unittest
from seattle_feeds.sources.elcorazon import ElCorazonSource, FunhouseSource

FIXTURE = """
<div class="event-card">
  <h3>Fear Factory - Cybernetic Domination Tour 2026</h3>
  <div>Darkest Hour, Brotality, Lacabra</div>
  <div>November 20, 2026</div><div>6:00 pm</div><div>7:00 pm</div>
  <div>El Corazón</div><div>All Ages</div>
  <a href="https://app.opendate.io/e/fear-factory-cybernetic-domination-tour-2026-november-20-2026-681148">Get Tickets</a>
</div>
<div class="event-card">
  <h3>Gully Boys - My Big Fat Gay Tour</h3>
  <div>Pollyanna, Black Ends</div>
  <div>November 7, 2026</div><div>7:00 pm</div><div>8:00 pm</div>
  <div>The Funhouse</div><div>All Ages</div>
  <a href="https://app.opendate.io/e/gully-boys-my-big-fat-gay-tour-november-07-2026-726563">Get Tickets</a>
</div>
"""

class ElCorazonTests(unittest.TestCase):
    def test_routes_el_corazon(self):
        events = ElCorazonSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_event_id, "681148")
        self.assertEqual(events[0].venue, "El Corazón")
        self.assertEqual(events[0].start_at.hour, 19)

    def test_routes_funhouse(self):
        events = FunhouseSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_event_id, "726563")
        self.assertEqual(events[0].venue, "The Funhouse")
        self.assertEqual(events[0].start_at.hour, 20)
