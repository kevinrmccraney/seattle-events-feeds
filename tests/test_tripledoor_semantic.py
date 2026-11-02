import unittest
from seattle_feeds.sources.tripledoor import TripleDoorSource

HTML = '''
<div class="event-detail">
<h3><a href="/go/events/111?occurrence_id=9001">Murray Hill &quot;Showbiz! The Tour&quot;</a></h3>
<div>Wednesday, November 4 @ 7:30PM Wed, Nov 4 @ 7:30PM</div>
<div>Mainstage Theatre, 216 Union Street, Seattle</div>
<a href="https://tickets.thetripledoor.net/eventperformances.asp?evt=1">Get tickets</a>
</div>
<div class="event-detail">
<h3><a href="/go/events/112?occurrence_id=9002">Golden &amp; Gay: 10th Annual Cabaret</a></h3>
<div>Saturday, November 7 @ 5:00PM</div><div>Mainstage Theatre, 216 Union Street, Seattle</div>
</div>
<div class="event-detail">
<h3><a href="/go/events/113?occurrence_id=9003">Dan Rodriguez at The Rabbit Box</a></h3>
<div>Saturday, November 7 @ 7:30PM</div><div>The Rabbit Box, Seattle, WA</div>
</div>
'''

class TripleDoorSemanticTests(unittest.TestCase):
    def test_mainstage_occurrences(self):
        events = TripleDoorSource.parse_listing(HTML, default_year=2026)
        self.assertEqual(len(events), 2)
        self.assertEqual({e.source_event_id for e in events}, {"9001", "9002"})
        self.assertTrue(all("Rabbit Box" not in e.title for e in events))

if __name__ == '__main__': unittest.main()
