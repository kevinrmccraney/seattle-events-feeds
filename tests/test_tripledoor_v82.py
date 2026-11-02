
import unittest
from seattle_feeds.sources.tripledoor import TripleDoorSource

LISTING = """
<a href="/go/events/6587306?feature_id=923529&occurrence_id=763958799&popup=1">
Murray Hill "Showbiz! The Tour" Mainstage Theatre, Seattle 7:30PM
</a>
<a href="/go/events/6627298?feature_id=923529&occurrence_id=768073647&popup=1">
Dan Rodriguez at The Rabbit Box The Rabbit Box, Seattle, WA 7:30PM
</a>
"""

DETAIL = """
<html><body>
<h2>Murray Hill "Showbiz! The Tour"</h2>
<div>Wednesday, November 4 @ 7:30PM</div>
<div>Mainstage Theatre, 216 Union Street, Seattle</div>
<a href="https://tickets.thetripledoor.net/example">Get tickets</a>
</body></html>
"""

RABBIT = """
<html><body>
<h2>Dan Rodriguez at The Rabbit Box</h2>
<div>Saturday, November 7 @ 7:30PM</div>
<div>The Rabbit Box, Seattle, WA</div>
</body></html>
"""

class TripleDoorV82Tests(unittest.TestCase):
    def test_extracts_occurrences(self):
        links = TripleDoorSource.extract_performance_links(LISTING)
        self.assertEqual([x[1] for x in links], ["763958799", "768073647"])

    def test_parses_mainstage_detail(self):
        e = TripleDoorSource.parse_detail(
            DETAIL,
            "https://www.thetripledoor.net/go/events/6587306?occurrence_id=763958799",
            "763958799",
            2026,
        )
        self.assertIsNotNone(e)
        self.assertEqual(e.source_event_id, "763958799")
        self.assertEqual(e.start_at.hour, 19)
        self.assertEqual(e.start_at.minute, 30)

    def test_excludes_rabbit_box_detail(self):
        e = TripleDoorSource.parse_detail(
            RABBIT,
            "https://www.thetripledoor.net/go/events/6627298?occurrence_id=768073647",
            "768073647",
            2026,
        )
        self.assertIsNone(e)

if __name__ == "__main__":
    unittest.main()
