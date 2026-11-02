import unittest
from seattle_feeds.sources.abbeyarts import FremontAbbeySource, BallardHomesteadSource

HOST = """
<div class="event-card">
  <a href="https://events.humanitix.com/11-5-the-moth">11/5 The Moth StorySLAM @ FREMONT ABBEY</a>
  <div>Thu, Nov 5, 8pm - 10:30pm PST</div>
  <div>Fremont Abbey Arts Center, Seattle WA, United States</div>
</div>
<div class="event-card">
  <a href="https://events.humanitix.com/26-11-14-wheresbeth">Where's Beth, Sarah Brunner, Karen Laura Peters @ BALLARD HOMESTEAD</a>
  <div>Sat, Nov 14, 7:30pm - 10pm PST</div>
  <div>Ballard Homestead, Seattle WA, United States</div>
</div>
<div class="event-card">
  <a href="https://events.humanitix.com/11-13-26-elanor-moss">CANCELLED: Elanor Moss @ BALLARD HOMESTEAD</a>
  <div>Fri, Nov 13, 7:30pm - 10pm PST</div>
  <div>Ballard Homestead, Seattle WA, United States</div>
</div>
"""

class AbbeyArtsV83Tests(unittest.TestCase):
    def test_fremont_host_inventory(self):
        events = FremontAbbeySource().parse_host(HOST)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "11/5 The Moth StorySLAM @ FREMONT ABBEY")

    def test_ballard_host_inventory(self):
        events = BallardHomesteadSource().parse_host(HOST)
        self.assertEqual(len(events), 2)
        cancelled = next(e for e in events if e.title.startswith("CANCELLED"))
        self.assertEqual(cancelled.status, "cancelled")

if __name__ == "__main__":
    unittest.main()
