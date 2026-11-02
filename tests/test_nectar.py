import unittest

from seattle_feeds.sources.nectar import NectarSource, HiddenHallSource


FIXTURE = """
<div class="event-card">
  <div>Sun Nov 01 2026</div>
  <div>Sean Healy presents:</div>
  <h3><a href="/events/daley">DALEY with Aryana León</a></h3>
  <h4>with Aryana Leon</h4>
  <div>7:30 PM</div>
  <div>Nectar Lounge</div><div>Seattle, WA</div>
  <div>Ages 21+</div>
  <a href="https://www.tixr.com/groups/nectarlounge/events/daley-with-aryana-le-n-187401">TICKETS</a>
</div>
<div class="event-card">
  <div>Sun Nov 01 2026</div>
  <div>Hidden Hall &amp; Solid Sound present:</div>
  <h3><a href="/events/rittz">RITTZ with Kung Fu Vampire, Jay Fiddy</a></h3>
  <h4>with Kung Fu Vampire &amp; Jay Fiddy &amp; Vic Daggs II</h4>
  <div>7:00 PM</div><div>Hidden Hall</div><div>Seattle, WA</div><div>Ages 21+</div>
  <a href="https://www.tixr.com/groups/nectarlounge/events/rittz-with-kung-fu-vampire-188888">TICKETS</a>
</div>
<div class="event-card">
  <div>Sun Nov 08 2026</div>
  <div>Hidden Hall, KEXP &amp; The PBJ Present AT NEUMOS:</div>
  <h3><a href="/events/genesis-owusu">GENESIS OWUSU SHOW MOVED TO NEUMOS</a></h3>
  <div>7:00 PM</div><div>Neumos</div><div>Seattle, WA</div><div>Ages 21+</div>
  <a href="https://www.tixr.com/groups/nectarlounge/events/genesis-owusu-199999">TICKETS</a>
</div>
"""


class NectarTests(unittest.TestCase):
    def test_nectar_routes_by_actual_venue(self):
        events = NectarSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.source_event_id, "187401")
        self.assertEqual(event.title, "DALEY with Aryana León")
        self.assertEqual(event.venue, "Nectar Lounge")
        self.assertEqual(event.support, "Aryana Leon")

    def test_hidden_hall_routes_by_actual_venue(self):
        events = HiddenHallSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.source_event_id, "188888")
        self.assertEqual(event.venue, "Hidden Hall")
        self.assertIn("Kung Fu Vampire", event.support)


if __name__ == "__main__":
    unittest.main()
