import unittest
from datetime import datetime

from seattle_feeds.sources.stg import UNLISTED_TIME, ParamountSource
from seattle_feeds.util import TZ


def card(title, date, venue, href, event_id, time=""):
    return f'''
    <article class="mec-event-article">
      <a data-event-id="{event_id}" href="{href}"><img src="https://www.stgpresents.org/photo.jpg"></a>
      <span class="mec-start-date-label">{date}</span>
      <div class="mec-event-time">{time}</div>
      <h3 class="mec-event-title"><a data-event-id="{event_id}" href="{href}">{title}</a></h3>
      <div class="mec-event-loc-place">{venue}</div>
    </article>
    '''


SETTINGS = '''
<script>
jQuery("#mec_skin_mec1").mecListView( {
  end_date: "2026-11-28",
  offset: "1",
  current_month_divider: "202611",
  atts: "atts%5Bsk-options%5D%5Blist%5D%5Bstyle%5D=classic&atts%5Bcategory%5D=21&atts%5Binstance_id%5D=mec1&atts%5Bid%5D=mec1"
});
</script>
'''

JOSH = "https://www.stgpresents.org/events/josh-johnsons-comedy-band-camp/"
TYLA = "https://www.stgpresents.org/events/tyla/"


class Response:
    def __init__(self, text="", payload=None, status=200):
        self.text = text
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self._payload


class Session:
    def __init__(self, first, payload):
        self.first = first
        self.payload = payload
        self.posts = []

    def get(self, url, timeout=30, headers=None):
        self.url = url
        return Response(self.first)

    def post(self, url, data=None, timeout=30, headers=None):
        self.posts.append((url, data, headers))
        return Response(payload=self.payload)


class STGCalendarTests(unittest.TestCase):
    def test_same_day_cards_stay_distinct_and_mark_missing_time(self):
        html = SETTINGS + card(
            "Josh Johnson’s Comedy Band Camp", "Nov 20 2026", "The Paramount Theatre", JOSH, "68825"
        ) + card(
            "Josh Johnson’s Comedy Band Camp", "Nov 20 2026", "The Paramount Theatre", JOSH, "68825"
        ) + card(
            "Tyla", "Nov 1 2026", "The Paramount Theatre", TYLA, "78843"
        ) + card(
            "Other Room", "Nov 20 2026", "The Neptune Theatre", "https://www.stgpresents.org/events/other/", "1"
        )
        source = ParamountSource()
        events = source.events_from_cards(source._cards(html))
        self.assertEqual([event.title for event in events], [
            "Josh Johnson’s Comedy Band Camp",
            "Josh Johnson’s Comedy Band Camp",
            "Tyla",
        ])
        self.assertEqual(events[0].doors_time, UNLISTED_TIME)
        self.assertEqual(events[1].doors_time, UNLISTED_TIME)
        self.assertNotEqual(events[0].source_event_id, events[1].source_event_id)
        self.assertTrue(events[0].source_event_id.endswith(":20261120:1"))
        self.assertTrue(events[1].source_event_id.endswith(":20261120:2"))
        self.assertEqual(events[0].metadata["occurrence_index"], 1)
        self.assertEqual(events[1].metadata["occurrence_index"], 2)
        self.assertFalse(events[0].metadata["show_time_listed"])
        self.assertEqual(events[0].start_at, datetime(2026, 11, 20, tzinfo=TZ))
        self.assertEqual(events[0].start_at.hour, 0)

    def test_listed_clock_time_is_kept(self):
        html = card(
            "Tyla", "Nov 17 2026", "The Paramount Theatre", TYLA, "78843", time="8:00 PM"
        )
        source = ParamountSource()
        event = source.events_from_cards(source._cards(html))[0]
        self.assertIsNone(event.doors_time)
        self.assertTrue(event.metadata["show_time_listed"])
        self.assertEqual(event.start_at, datetime(2026, 11, 17, 20, 0, tzinfo=TZ))
        self.assertNotIn(":1", event.source_event_id)

    def test_fetch_follows_one_load_more_page_and_keeps_today(self):
        first = SETTINGS + card(
            "Tyla", "Nov 17 2026", "The Paramount Theatre", TYLA, "78843"
        ) + card(
            "Already Over", "Nov 1 2026", "The Paramount Theatre", "https://www.stgpresents.org/events/over/", "2"
        )
        more = card(
            "Later", "Dec 1 2026", "The Paramount Theatre", "https://www.stgpresents.org/events/later/", "9", time="7:30 PM"
        )
        session = Session(first, {
            "count": 1,
            "html": more,
            "end_date": "2026-12-01",
            "offset": "2",
            "current_month_divider": "202612",
            "has_more_event": 0,
        })
        events = ParamountSource().fetch_events(session, datetime(2026, 11, 17, 15, tzinfo=TZ))
        self.assertEqual(session.url, "https://www.stgpresents.org/event-category/paramount/")
        self.assertEqual(len(session.posts), 1)
        self.assertEqual(session.posts[0][1]["action"], "mec_list_load_more")
        self.assertEqual(session.posts[0][1]["mec_start_date"], "2026-11-28")
        self.assertEqual(session.posts[0][1]["atts[category]"], "21")
        self.assertEqual([event.title for event in events], ["Tyla", "Later"])
        self.assertEqual(events[0].doors_time, UNLISTED_TIME)
        self.assertEqual(events[0].start_at, datetime(2026, 11, 17, tzinfo=TZ))
        self.assertIsNone(events[1].doors_time)
        self.assertEqual(events[1].start_at, datetime(2026, 12, 1, 19, 30, tzinfo=TZ))


if __name__ == "__main__":
    unittest.main()
