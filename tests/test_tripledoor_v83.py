import unittest
from seattle_feeds.sources.tripledoor import TripleDoorSource

PAGE = """
<div class="calendar-detail">
  <h2><a href="/go/events/6587306?feature_id=923529&occurrence_id=763958799&popup=1">Murray Hill "Showbiz! The Tour"</a></h2>
  <div>Wednesday, November 4 @ 7:30PM Wed, Nov 4 @ 7:30PM</div>
  <div>Mainstage Theatre, 216 Union Street, Seattle</div>
  <a href="https://tickets.thetripledoor.net/example">Get tickets</a>
</div>
<div class="calendar-detail">
  <h2><a href="/go/events/6714753?feature_id=923529&occurrence_id=777882362&popup=1">Dan Rodriguez at The Rabbit Box</a></h2>
  <div>Saturday, November 7 @ 7:30PM</div>
  <div>The Rabbit Box, 94 Pike St, Seattle, WA</div>
</div>
<a href="/mainstage-calendar?calendar_page=2">Next</a>
"""

class TripleDoorV83Tests(unittest.TestCase):
    def test_parses_paginated_detail_blocks(self):
        events = TripleDoorSource.parse_detail_list(PAGE, default_year=2026)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e.source_event_id, "763958799")
        self.assertEqual(e.title, 'Murray Hill "Showbiz! The Tour"')
        self.assertEqual(e.start_at.hour, 19)
        self.assertEqual(e.start_at.minute, 30)

    def test_follows_next_link(self):
        self.assertEqual(
            TripleDoorSource.next_page_url(PAGE),
            "https://www.thetripledoor.net/mainstage-calendar?calendar_page=2",
        )

if __name__ == "__main__":
    unittest.main()
