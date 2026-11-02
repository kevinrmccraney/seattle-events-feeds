import unittest
from seattle_feeds.sources.abbeyarts import FremontAbbeySource, BallardHomesteadSource

HTML = """
<a href="/11-5-the-moth">Thu, Nov 5, 8pm - 10:30pm PST 11/5 The Moth StorySLAM @ FREMONT ABBEY Seattle Fremont Abbey Arts Center, Seattle WA, United States</a>
<a href="/the-suitcase-junket">Sat, Nov 7, 7:30pm - 10pm PST The Suitcase Junket, Erika Lundahl @ BALLARD HOMESTEAD Ballard Homestead, Seattle WA, United States</a>
<a href="/lila-forde">Mon, Nov 9, 8pm - 10pm PST Lila Forde, Zan Fiskum @ FREMONT ABBEY Fremont Abbey Arts Center, Seattle WA, United States</a>
<a href="/elanor-moss">Fri, Nov 13, 7:30pm - 10pm PST CANCELLED: Elanor Moss @ BALLARD HOMESTEAD Ballard Homestead, Seattle WA, United States</a>
"""

class AbbeyArtsV84Tests(unittest.TestCase):
    def test_fremont(self):
        events = FremontAbbeySource().parse_host(HTML)
        self.assertEqual(len(events), 2)

    def test_ballard(self):
        events = BallardHomesteadSource().parse_host(HTML)
        self.assertEqual(len(events), 2)
        cancelled = next(e for e in events if e.title.startswith("CANCELLED"))
        self.assertEqual(cancelled.status, "cancelled")

if __name__ == "__main__":
    unittest.main()
