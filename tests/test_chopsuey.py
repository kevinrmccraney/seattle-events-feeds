import unittest
from seattle_feeds.sources.chopsuey import ChopSueySource
HTML="""<article><h3>Best, The Linens, Deep Contact</h3><div>Wed 11.4</div><div>Doors: 7:00 PM / Show: 8:00 PM</div><a href="/events/x">More Info</a><a href="https://tickets.example/x">Buy Tickets</a></article><article><h3>Flammable</h3><div>Sun 11.8</div><div>Show: 10:00 PM</div><a href="/events/y">More Info</a><a href="https://tickets.example/y">Buy Tickets</a></article>"""
class T(unittest.TestCase):
    def test_parse(self):
        e=ChopSueySource.parse_listing(HTML,2026); self.assertEqual(len(e),2)
        x=next(x for x in e if x.title.startswith("Best")); self.assertEqual(x.doors_time,"7:00 PM"); self.assertEqual(x.start_at.hour,20)
