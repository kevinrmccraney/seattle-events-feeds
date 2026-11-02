import unittest
from seattle_feeds.sources.jazzalley import JazzAlleySource

CAL = '''
<div class="calendar-row">
  <h3><a href="/www-home/artist.jsp?shownum=8831">Kenny Garrett and Sounds From The Ancestors</a></h3>
  <div>Tue, Nov 3 - Wed, Nov 4, 2026</div>
  <p>Grammy-award winning saxophonist Kenny Garrett.</p>
  <a href="/www-home/artist.jsp?shownum=8831">info</a>
</div>
'''

DETAIL = '''
<h1>Kenny Garrett and Sounds From The Ancestors</h1>
<p>Dimitriou's Jazz Alley welcomes Grammy-winning alto saxophonist Kenny Garrett for two nights. Showtimes Tuesday and Wednesday at 7:30pm. Doors open at 6:00pm nightly.</p>
<p>All sets are all ages.</p>
'''

class JazzAlleyTests(unittest.TestCase):
    def test_calendar_finds_date_outside_anchor_parent(self):
        rows = JazzAlleySource.parse_calendar(CAL)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_event_id"], "8831")
        self.assertEqual(rows[0]["start_date"], "Tue, Nov 3, 2026")
        self.assertEqual(rows[0]["end_date"], "Wed, Nov 4, 2026")

    def test_detail_and_performance_expansion(self):
        item = JazzAlleySource.parse_calendar(CAL)[0]
        detail = JazzAlleySource.parse_detail(DETAIL)
        self.assertEqual(detail["times"], ["7:30PM"])
        self.assertEqual(detail["doors_time"], "6:00PM")
        perfs = JazzAlleySource.expand_performances(item, detail)
        self.assertEqual([p.strftime("%Y-%m-%d %H:%M") for p in perfs], [
            "2026-11-03 19:30", "2026-11-04 19:30"
        ])

if __name__ == "__main__":
    unittest.main()
