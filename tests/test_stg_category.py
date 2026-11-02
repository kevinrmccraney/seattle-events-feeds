import unittest
from seattle_feeds.sources.stg import ParamountSource, NeptuneSource, MooreSource

HTML = """
<article>
  <div>Nov 03 2026</div>
  <h4><a href="/events/oh-mary/">Oh, Mary!</a></h4>
  <div>7:30 PM</div>
  <div>The Paramount Theatre</div>
</article>
<article>
  <div>Nov 04 2026</div>
  <h4><a href="/events/oh-mary/">Oh, Mary!</a></h4>
  <div>7:30 PM</div>
  <div>The Paramount Theatre</div>
</article>
<article>
  <div>Nov 07 2026</div>
  <h4><a href="/events/oh-mary/">Oh, Mary!</a></h4>
  <div>2:00 PM</div>
  <div>The Paramount Theatre</div>
</article>
<article>
  <div>Nov 07 2026</div>
  <h4><a href="/events/oh-mary/">Oh, Mary!</a></h4>
  <div>8:00 PM</div>
  <div>The Paramount Theatre</div>
</article>
<article>
  <div>Nov 07 2026</div>
  <h4><a href="/events/free-paramount-tour/">Free Paramount Tour</a></h4>
  <div>10:00 AM</div>
  <div>The Paramount Theatre</div>
</article>
<article>
  <div>Nov 03 2026</div>
  <h4><a href="/events/the-aces/">The Aces (RESCHEDULED)</a></h4>
  <div>8:00 PM</div>
  <div>The Neptune Theatre</div>
</article>
<article>
  <div>Nov 14 2026</div>
  <h4><a href="/events/ron-funches/">Ron Funches</a></h4>
  <div>7:00 PM</div>
  <div>The Neptune Theatre</div>
</article>
<article>
  <div>Nov 14 2026</div>
  <h4><a href="/events/ron-funches/">Ron Funches</a></h4>
  <div>9:30 PM</div>
  <div>The Neptune Theatre</div>
</article>
<article>
  <div>Nov 06 2026</div>
  <h4><a href="/events/periphery/">Periphery</a></h4>
  <div>6:30 PM</div>
  <div>The Moore Theatre</div>
</article>
<article>
  <div>Nov 24 2026</div>
  <h4><a href="/events/prateek-kuhad/">Prateek Kuhad – CANCELED</a></h4>
  <div>7:00 PM</div>
  <div>The Moore Theatre</div>
</article>
"""

class STGCategoryTests(unittest.TestCase):
    def test_paramount_all_occurrences(self):
        events = ParamountSource().parse_listing(HTML)
        self.assertEqual(len(events), 4)
        self.assertEqual(len({e.source_event_id for e in events}), 4)
        nov7 = [e for e in events if e.start_at.day == 7]
        self.assertEqual({(e.start_at.hour, e.start_at.minute) for e in nov7}, {(14, 0), (20, 0)})

    def test_neptune_duplicate_day_performances(self):
        events = NeptuneSource().parse_listing(HTML)
        self.assertEqual(len(events), 3)
        self.assertTrue(any(e.status == "rescheduled" for e in events))
        ron = [e for e in events if e.title == "Ron Funches"]
        self.assertEqual(len(ron), 2)

    def test_moore_cancelled(self):
        events = MooreSource().parse_listing(HTML)
        self.assertEqual(len(events), 2)
        cancelled = next(e for e in events if "Prateek" in e.title)
        self.assertEqual(cancelled.status, "cancelled")

if __name__ == "__main__":
    unittest.main()
