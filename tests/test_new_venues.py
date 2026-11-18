import unittest
from datetime import datetime

from seattle_feeds.sources.seamonster import SeaMonsterSource
from seattle_feeds.sources.substation import SubstationSource
from seattle_feeds.util import TZ


class SeaMonsterTests(unittest.TestCase):
    def test_timestamped_url_and_text_time(self):
        html = '''
        <li data-hook="event-list-item">
          <span data-hook="ev-list-item-title">Foleada</span>
          <a href="https://www.seamonsterlounge.com/event-info/foleada-2026-11-17-19-00">RSVP</a>
        </li>
        <li data-hook="event-list-item">
          <span data-hook="ev-list-item-title">Skerik’s Birthday</span>
          <a href="https://www.seamonsterlounge.com/event-info/skeriks-birthday-crack-sabbath">RSVP</a>
          Nov 19, 2026, 7:00 PM – 9:00 PM
        </li>
        '''
        events = SeaMonsterSource.parse_listing(html)
        self.assertEqual(events[0].start_at, datetime(2026, 11, 17, 19, 0, tzinfo=TZ))
        self.assertEqual(events[1].start_at, datetime(2026, 11, 19, 19, 0, tzinfo=TZ))
        self.assertNotEqual(events[0].id, events[1].id)


class SubstationSiteTests(unittest.TestCase):
    def test_card_uses_the_clock_time(self):
        html = '''
        <article class="event">
          <time datetime="2026-11-17T19:00:00">7:00 PM</time>
          <h3>Agriculture</h3>
          <a href="https://www.eventbrite.com/e/agriculture-tickets-1992395887734">Get Tickets</a>
        </article>
        '''
        event = SubstationSource.parse_listing(html)[0]
        self.assertEqual(event.title, "Agriculture")
        self.assertEqual(event.venue, "Substation")
        self.assertEqual(event.start_at, datetime(2026, 11, 17, 19, 0, tzinfo=TZ))
        self.assertIn("eventbrite.com/e/agriculture-tickets-1992395887734", event.event_url)


if __name__ == "__main__":
    unittest.main()
