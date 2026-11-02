import unittest
from datetime import datetime

from seattle_feeds.sources.carbonhouse import CarbonhouseSource
from seattle_feeds.sources.dice import DiceVeraSource
from seattle_feeds.sources.showbox import ShowboxSource
from seattle_feeds.sources.tractor import TractorSource
from seattle_feeds.sources.clockout import ClockOutSource
from seattle_feeds.util import TZ


class CarbonhouseTests(unittest.TestCase):
    def test_barboza_batch(self):
        html = '''
        <div class="eventItem entry clearfix">
          <div class="thumb"><a href="https://www.thebarboza.com/events/detail/trask-tickets-1636462"><img src="https://example.com/trask.jpg"></a></div>
          <div class="info clearfix">
            <div class="promotion-text">Barboza Presents</div>
            <h3 class="title title-withTagline"><a href="https://www.thebarboza.com/events/detail/trask-tickets-1636462">Trask</a></h3>
            <h4 class="tagline">Dining Dead + Cal State Football</h4>
            <div class="date barboza" aria-label="December 6 2026"></div>
            <div class="meta">
              <div class="time">Doors: 6:00 PM</div>
              <div class="age">21 &amp; Over</div>
              <div class="location barboza">Barboza</div>
            </div>
          </div>
          <div class="buttons"><a href="https://www.axs.com/events/1636462/trask-tickets?skin=barboza" class="tickets onsalenow" data-canceled="false">Buy Tickets</a></div>
        </div>
        '''
        source = CarbonhouseSource("barboza", "Barboza", "https://www.thebarboza.com", "Barboza")
        events = source.parse_batch(html)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.id, "barboza:1636462")
        self.assertEqual(event.title, "Trask")
        self.assertEqual(event.support, "Dining Dead + Cal State Football")
        self.assertEqual(event.doors_time, "6:00 PM")
        self.assertEqual(event.venue, "Barboza")
        self.assertEqual(event.status, "scheduled")

    def test_neumos_uses_default_venue_and_cancelled(self):
        html = '''
        <div class="eventItem entry clearfix">
          <div class="info clearfix">
            <div class="promotion-text">Neumos Presents</div>
            <h3 class="title"><a href="https://www.neumos.com/events/detail/test-band-tickets-1234567">Test Band</a></h3>
            <div class="date neumos" aria-label="November 13 2026"></div>
            <div class="meta"><div class="time">Doors: 9:00 PM</div><div class="age">21 &amp; Over</div></div>
          </div>
          <div class="buttons"><a href="https://www.axs.com/events/1234567/test-band" class="tickets" data-canceled="true">Cancelled</a></div>
        </div>
        '''
        source = CarbonhouseSource("neumos", "Neumos", "https://www.neumos.com", "Neumos")
        event = source.parse_batch(html)[0]
        self.assertEqual(event.venue, "Neumos")
        self.assertEqual(event.status, "cancelled")


class DiceTests(unittest.TestCase):
    def test_normalize_music_event(self):
        raw = {
            "id": "6a69113fbb5b8700016b87f8",
            "name": "Kingdom of Giants",
            "type_tags": ["music:gig"],
            "date": "2026-11-15T03:00:00Z",
            "date_end": "2026-11-15T07:00:00Z",
            "venue": "The Vera Project",
            "url": "https://link.dice.fm/example",
            "description": "The Vera Project Presents Kingdom of Giants",
            "age_limit": "This is an All Ages event.",
            "sold_out": False,
            "status": "on-sale",
            "flags": ["going_ahead"],
            "artists": ["Kingdom of Giants", "Deadlands"],
            "genre_tags": ["gig:metal"],
            "address": "305 Harrison Street, Seattle, Washington 98109, United States",
            "presented_by": "Presented by The Vera Project.",
            "lineup": [{"details": "Doors open", "time": "7:00 PM"}],
            "event_images": {"landscape": "https://example.com/image.jpg"},
            "checksum": "abc",
        }
        event = DiceVeraSource._normalize(raw)
        self.assertEqual(event.id, "vera:6a69113fbb5b8700016b87f8")
        self.assertEqual(event.venue, "The Vera Project")
        self.assertEqual(event.doors_time, "7:00 PM")
        self.assertEqual(event.support, "Deadlands")
        self.assertEqual(event.metadata["genre_tags"], ["gig:metal"])


class ShowboxTests(unittest.TestCase):
    def test_seattle_only_and_cancelled(self):
        html = '''
        <div class="event-card">
          <h5>Showbox Presents</h5><h5>Tour Name</h5>
          <h3><a href="/events/detail/test">Test Artist</a></h3>
          <h4>with Support Artist</h4>
          <p>Sat, Nov 7, 2026 Show 8:00 PM @ The Showbox</p>
          <a href="https://www.axs.com/events/1/test">Buy Tickets</a>
        </div>
        <div class="event-card">
          <h5>Showbox Presents</h5>
          <h3><a href="/events/detail/portland">Portland Artist</a></h3>
          <p>Sun, Nov 8, 2026 Show 8:00 PM @ Wonder Ballroom</p>
          <a href="https://www.axs.com/events/2/test">Buy Tickets</a>
        </div>
        <div class="event-card">
          <h5>Showbox Presents</h5>
          <h3><a href="/events/detail/cancelled">Cancelled Artist</a></h3>
          <p>Mon, Nov 30, 2026 Show 8:00 PM @ Showbox SoDo</p>
          <a href="https://www.axs.com/events/3/test">Cancelled</a>
        </div>
        '''
        start = datetime(2026, 10, 31, tzinfo=TZ)
        end = datetime(2027, 1, 29, tzinfo=TZ)
        events = ShowboxSource().parse_html(html, start, end)
        self.assertEqual({e.title for e in events}, {"Test Artist", "Cancelled Artist"})
        first = next(e for e in events if e.title == "Test Artist")
        self.assertEqual(first.support, "Support Artist")
        self.assertEqual(first.promoter, "Showbox Presents")
        cancelled = next(e for e in events if e.title == "Cancelled Artist")
        self.assertEqual(cancelled.status, "cancelled")

    def test_showbox_identity_does_not_change_with_date(self):
        html_a = """
        <div class="event-card">
          <h5>Showbox Presents</h5>
          <h3><a href="/events/detail/test">Test Artist</a></h3>
          <p>Sat, Nov 7, 2026 Show 8:00 PM @ The Showbox</p>
          <a href="https://www.axs.com/events/123456/test">Buy Tickets</a>
        </div>
        """
        html_b = html_a.replace("Nov 7, 2026", "Nov 14, 2026")
        start = datetime(2026, 10, 31, tzinfo=TZ)
        a = ShowboxSource().parse_html(html_a, start)[0]
        b = ShowboxSource().parse_html(html_b, start)[0]
        self.assertEqual(a.source_event_id, "123456")
        self.assertEqual(a.id, b.id)


class TractorTests(unittest.TestCase):
    def test_parse_listing_filters_other_promoted_venues(self):
        html = '''
        <div class="event-card">
          <img src="https://example.com/tractor.jpg">
          <a href="/e/jeffrey-martin-w-sam-weber-partially-seated-november-04-2026-761590">Jeffrey Martin w/ Sam Weber (partially seated)</a>
          <div>with Sam Weber</div>
          <div>November 04, 2026</div>
          <div>Doors: 7:00 PM - Show: 8:00 PM</div>
          <div>Tractor Tavern • Seattle, WA</div>
        </div>
        <div class="event-card">
          <a href="/e/tractor-presents-babehoven-at-the-sunset-november-17-2026-999999">Tractor Presents: Babehoven w/ Pileup AT The Sunset</a>
          <div>with Pileup</div>
          <div>November 17, 2026</div>
          <div>Doors: 7:30 PM - Show: 8:00 PM</div>
          <div>Sunset Tavern • Seattle, WA</div>
        </div>
        <a href="?layout=iframe&page=2">→</a>
        '''
        events = TractorSource.parse_listing(html)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.id, "tractor:761590")
        self.assertEqual(event.source_event_id, "761590")
        self.assertEqual(event.title, "Jeffrey Martin w/ Sam Weber (partially seated)")
        self.assertEqual(event.support, "Sam Weber")
        self.assertEqual(event.venue, "Tractor Tavern")
        self.assertEqual(event.doors_time, "7:00 PM")
        self.assertEqual(event.start_at.hour, 20)
        self.assertEqual(event.ticket_url, event.event_url)

    def test_sold_out_and_identity(self):
        html = '''
        <div class="event-card">
          <span>SOLD OUT</span>
          <a href="https://app.opendate.io/e/test-show-january-29-2027-761641">SOLD OUT! Test Show</a>
          <div>January 29, 2027</div>
          <div>Doors: 5:00 PM - Show: 6:00 PM</div>
          <div>Tractor Tavern • Seattle, WA</div>
        </div>
        '''
        event = TractorSource.parse_listing(html)[0]
        self.assertTrue(event.sold_out)
        self.assertEqual(event.source_event_id, "761641")



if __name__ == "__main__":
    unittest.main()
