import unittest
from datetime import datetime

from seattle_feeds.sources.zoo import WoodlandParkZooSource, is_closure
from seattle_feeds.util import TZ


def event(title, utc="2026-11-20 00:00:00", url="https://zoo.org/event/wildlanterns/2026-11-19/"):
    return {
        "id": 100,
        "title": title,
        "status": "publish",
        "utc_start_date": utc,
        "url": url,
        "venue": {"venue": "Woodland Park Zoo"},
    }


class ZooTests(unittest.TestCase):
    def test_closure_notices_are_dropped(self):
        self.assertTrue(is_closure("Early Closure"))
        self.assertTrue(is_closure("Zoo Closed"))
        self.assertFalse(is_closure("WildLanterns presented by Kaiser Permanente"))
        self.assertFalse(is_closure("Enclosure Tour"))
        events = WoodlandParkZooSource.events_from_payload({
            "events": [
                event("WildLanterns presented by Kaiser Permanente"),
                event("Early Closure", utc="2026-11-26 17:30:00", url="https://zoo.org/event/early-closure-2/"),
                event("WildLanterns:  21+ Night Owls", utc="2026-11-21 00:00:00", url="https://zoo.org/event/night-owls/2026-11-20/"),
            ]
        })
        self.assertEqual([item.title for item in events], [
            "WildLanterns presented by Kaiser Permanente",
            "WildLanterns: 21+ Night Owls",
        ])
        self.assertEqual(events[0].start_at, datetime(2026, 11, 19, 16, 0, tzinfo=TZ))
        self.assertEqual(events[1].age_restriction, "21+")
        self.assertEqual(events[0].venue, "Woodland Park Zoo")

    def test_fetch_follows_the_next_page(self):
        pages = [
            {
                "events": [event("Holiday Senior Stroll", url="https://zoo.org/event/holiday-senior-stroll/")],
                "next_rest_url": "https://zoo.org/wp-json/tribe/events/v1/events?page=2",
            },
            {
                "events": [event("Early Closure", url="https://zoo.org/event/early-closure-2/")],
                "next_rest_url": "",
            },
        ]

        class Response:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class Session:
            def __init__(self):
                self.calls = []

            def get(self, url, params=None, timeout=30):
                self.calls.append((url, params))
                return Response(pages[len(self.calls) - 1])

        session = Session()
        events = WoodlandParkZooSource().fetch_events(session, datetime(2026, 11, 17, 15, tzinfo=TZ))
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[0][1]["start_date"], "2026-11-17")
        self.assertIsNone(session.calls[1][1])
        self.assertEqual([item.title for item in events], ["Holiday Senior Stroll"])


if __name__ == "__main__":
    unittest.main()
