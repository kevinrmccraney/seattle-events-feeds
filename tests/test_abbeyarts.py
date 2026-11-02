import unittest
from seattle_feeds.sources.abbeyarts import FremontAbbeySource, BallardHomesteadSource

FIXTURE='''
<div>
<a href="https://events.humanitix.com/26-11-5-moth">Thu, Nov 5, 8pm - 10:30pm PST 11/5 The Moth StorySLAM @ FREMONT ABBEY Seattle Fremont Abbey Arts Center, Seattle WA, United States</a>
<a href="https://events.humanitix.com/26-11-7-suitcasejunket">Sat, Nov 7, 7:30pm - 10pm PST The Suitcase Junket, Erika Lundahl @ BALLARD HOMESTEAD Ballard Homestead, Seattle WA, United States</a>
<a href="https://events.humanitix.com/26-11-13-elanor">Fri, Nov 13, 7:30pm - 10pm PST CANCELLED: Elanor Moss @ BALLARD HOMESTEAD Ballard Homestead, Seattle WA, United States</a>
</div>
'''

class AbbeyArtsTests(unittest.TestCase):
    def test_fremont(self):
        events=FremontAbbeySource().parse_collection(FIXTURE,default_year=2026)
        self.assertEqual(len(events),1)
        self.assertIn('Moth StorySLAM',events[0].title)
        self.assertEqual(events[0].start_at.hour,20)

    def test_ballard_and_cancelled(self):
        events=BallardHomesteadSource().parse_collection(FIXTURE,default_year=2026)
        self.assertEqual(len(events),2)
        cancelled=[e for e in events if e.status=='cancelled']
        self.assertEqual(len(cancelled),1)
        self.assertEqual(cancelled[0].source_event_id,'26-11-13-elanor')

if __name__ == '__main__':
    unittest.main()
