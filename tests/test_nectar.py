import unittest

from seattle_feeds.sources.nectar import NectarSource, HiddenHallSource


FIXTURE = '''
<div class="event-card">
  <div class="date">Sun Nov 01 2026</div>
  <div class="promoter">Sean Healy presents:</div>
  <h3><a href="https://www.tixr.com/groups/nectarlounge/events/daley-with-aryana-le-n-187401">DALEY with Aryana León</a></h3>
  <h4>with Aryana Leon</h4>
  <div class="time">7:30 PM</div>
  <div class="venue">Nectar Lounge</div><div>Seattle, WA</div>
  <div>Ages 21+ <a href="https://www.tixr.com/groups/nectarlounge/events/daley-with-aryana-le-n-187401">TICKETS</a></div>
</div>
<div class="event-card">
  <div>Sun Nov 01 2026</div>
  <div>Hidden Hall &amp; Solid Sound present:</div>
  <h3><a href="https://www.tixr.com/groups/nectarlounge/events/rittz-with-kung-fu-vampire-188888">RITTZ with Kung Fu Vampire, Jay Fiddy</a></h3>
  <h4>with Kung Fu Vampire &amp; Jay Fiddy &amp; Vic Daggs II</h4>
  <div>7:00 PM</div><div>Hidden Hall</div><div>Seattle, WA</div><div>Ages 21+</div>
</div>
<div class="event-card">
  <div>Sun Nov 08 2026</div>
  <div>Hidden Hall, KEXP &amp; The PBJ Present AT NEUMOS:</div>
  <h3><a href="https://www.tixr.com/groups/nectarlounge/events/genesis-owusu-199999">GENESIS OWUSU SHOW MOVED TO NEUMOS</a></h3>
  <div>7:00 PM</div><div>Neumos</div><div>Seattle, WA</div><div>Ages 21+</div>
</div>
'''


class NectarTests(unittest.TestCase):
    def test_nectar_routes_only_nectar_lounge(self):
        events = NectarSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.id, "nectar:187401")
        self.assertEqual(event.title, "DALEY with Aryana León")
        self.assertEqual(event.support, "Aryana Leon")
        self.assertEqual(event.venue, "Nectar Lounge")
        self.assertEqual(event.age_restriction, "Ages 21+")
        self.assertEqual(event.metadata["platform"], "tixr")

    def test_hidden_hall_routes_only_hidden_hall_and_excludes_moved_show(self):
        events = HiddenHallSource().parse_calendar(FIXTURE)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.id, "hidden-hall:188888")
        self.assertEqual(event.venue, "Hidden Hall")
        self.assertIn("Kung Fu Vampire", event.support)


if __name__ == "__main__":
    unittest.main()
