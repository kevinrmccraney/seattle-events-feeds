import unittest
from datetime import datetime

from seattle_feeds.sources.chopsuey import ChopSueySource
from seattle_feeds.util import TZ

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

    def test_site_widget_uses_show_time_and_rolls_the_year(self):
        html = '''
        <div class="tw-plugin-upcoming-event-list">
          <div class="row">
            <div class="tw-name"><a href="/tm-event/dead-butterflies/">Dead Butterflies</a></div>
            <span class="tw-event-date">11.17</span>
            <span class="tw-event-door-time">6:00 PM</span>
            <span class="tw-event-time">Show: 7:00 PM</span>
          </div>
          <div class="row">
            <div class="tw-name"><a href="/tm-event/january-show/">January Show</a></div>
            <span class="tw-event-date">1.10</span>
            <span class="tw-event-time">Show: 8:00 PM</span>
          </div>
        </div>
        '''
        events = ChopSueySource.parse_site(html, datetime(2026, 11, 17, 15, tzinfo=TZ))
        by_title = {event.title: event for event in events}
        self.assertEqual(by_title["Dead Butterflies"].start_at, datetime(2026, 11, 17, 19, 0, tzinfo=TZ))
        self.assertEqual(by_title["Dead Butterflies"].doors_time, "6:00 PM")
        self.assertEqual(by_title["Dead Butterflies"].event_url, "https://chopsuey.com/tm-event/dead-butterflies/")
        self.assertEqual(by_title["January Show"].start_at, datetime(2027, 1, 10, 20, 0, tzinfo=TZ))
        self.assertIsNone(by_title["January Show"].doors_time)

if __name__ == '__main__': unittest.main()
