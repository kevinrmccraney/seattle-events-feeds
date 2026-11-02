import unittest
from seattle_feeds.sources.abbeyarts import FremontAbbeySource, BallardHomesteadSource

HTML = """
<html><body>
<div id="app">
Events Upcoming Past
Thu, Nov 5, 8pm - 10:30pm PST 11/5 The Moth StorySLAM @ FREMONT ABBEY Seattle Fremont Abbey Arts Center, Seattle WA, United States
Sat, Nov 7, 7:30pm - 10pm PST The Suitcase Junket, Erika Lundahl @ BALLARD HOMESTEAD Ballard Homestead, Seattle WA, United States
Mon, Nov 9, 8pm - 10pm PST Lila Forde, Zan Fiskum @ FREMONT ABBEY Fremont Abbey Arts Center, Seattle WA, United States
Tue, Nov 10, 6:30pm - 9:30pm PST Realization Process Workshop @ BALLARD HOMESTEAD Ballard Homestead, Seattle WA, United States
Fri, Nov 13, 7:30pm - 10pm PST CANCELLED: Elanor Moss @ BALLARD HOMESTEAD Ballard Homestead, Seattle WA, United States
Sat, Nov 14, 7:30pm - 10pm PST Where's Beth, Sarah Brunner, Karen Laura Peters @ BALLARD HOMESTEAD Ballard Homestead, Seattle WA, United States
</div>
</body></html>
"""

class AbbeyArtsV85Tests(unittest.TestCase):
    def test_fremont_text_fallback(self):
        events = FremontAbbeySource().parse_host(HTML)
        self.assertGreaterEqual(len(events), 2)

    def test_ballard_text_fallback(self):
        events = BallardHomesteadSource().parse_host(HTML)
        self.assertGreaterEqual(len(events), 4)
        self.assertTrue(any(e.status == "cancelled" for e in events))

if __name__ == "__main__":
    unittest.main()
