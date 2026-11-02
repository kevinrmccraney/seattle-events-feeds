import unittest
from seattle_feeds.sources.centralsaloon import CentralSaloonSource
HTML="""<h4>November 2026</h4><article><h3>The Entourage • Killbilly • Analog Citizens</h3><div>SUNDAY</div><div>01 Nov</div><div>7:00 pm</div><a href="/events/one">View Detail</a></article><article><h3>Askysoblack • O Miles Per Hour • Commoner • Bonny Rubble</h3><div>MONDAY</div><div>09 Nov</div><div>7:00 pm</div><a href="/events/two">View Detail</a></article>"""
class T(unittest.TestCase):
    def test_parse(self):
        e=CentralSaloonSource.parse_listing(HTML,2026); self.assertEqual(len(e),2); self.assertTrue(all(x.start_at.year==2026 for x in e))
