import unittest
from seattle_feeds.sources.chopsuey import ChopSueySource

HTML = '''
<div class="event-card">
 <h3><a href="https://www.ticketweb.com/event/best-the-linens-deep-contact-chop-suey-tickets/123">Best, The Linens, Deep Contact</a></h3>
 <div>Wed Nov 4 2026</div><div>8:00 PM</div><div>Doors 7:00 PM</div>
 <a href="https://www.ticketweb.com/event/best-the-linens-deep-contact-chop-suey-tickets/123">Find Tickets</a>
</div>
<div class="event-card">
 <h3><a href="/event/flammable-chop-suey-tickets/124">Flammable</a></h3>
 <div>Sun Nov 8</div><div>10:00 PM</div>
 <a href="/event/flammable-chop-suey-tickets/124">Find Tickets</a>
</div>
'''

class ChopSueySemanticTests(unittest.TestCase):
    def test_ticketweb_cards(self):
        events = ChopSueySource.parse_listing(HTML, 2026)
        self.assertEqual(len(events), 2)
        first = next(e for e in events if e.title.startswith("Best"))
        self.assertEqual(first.doors_time, "7:00 PM")
        self.assertIn("/event/", first.event_url)

if __name__ == '__main__': unittest.main()
