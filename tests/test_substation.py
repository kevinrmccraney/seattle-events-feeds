import unittest
from seattle_feeds.sources.substation import SubstationSource
HTML="""<article><div>Wednesday November 4, 2026 9:00 PM</div><h3><a href="/event/cut-copy">Cut Copy (DJ Set)</a></h3><p>Award-winning Cut Copy is bringing synth-pop dance music straight to Substation.</p><div>Indie</div><a href="https://tickets.example/cut">Get Tickets</a></article><article><div>Thursday November 5, 2026 9:00 PM</div><h3><a href="/event/izzy-vadim">Izzy Vadim</a></h3><p>Izzy Vadim is bringing mind-melting dubstep and halftime heaters to Substation, with support from crysomemore and Slim Chance.</p><div>EDM / Electronic</div><a href="https://tickets.example/izzy">Get Tickets</a></article>"""
class T(unittest.TestCase):
    def test_parse(self):
        e=SubstationSource.parse_listing(HTML); self.assertEqual(len(e),2)
        x=next(x for x in e if x.title=="Izzy Vadim"); self.assertEqual(x.support,"crysomemore and Slim Chance")
