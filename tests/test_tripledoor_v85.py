import unittest
from seattle_feeds.sources.tripledoor import TripleDoorSource

HTML = """
<div class="performance">
  <h3><a href="/eventperformances.asp?evt=2201">Murray Hill "Showbiz! The Tour"</a></h3>
  <div>Wednesday, November 4, 2026 7:30 PM</div>
  <div>The Triple Door Seattle, WA</div>
  <a href="/eventperformances.asp?evt=2201">Buy Tickets</a>
</div>
<div class="performance">
  <h3><a href="/eventperformances.asp?evt=2284">Dan Rodriguez at The Rabbit Box</a></h3>
  <div>Saturday, November 7, 2026 7:30 PM</div>
  <div>The Triple Door Seattle, WA</div>
  <a href="/eventperformances.asp?evt=2284">Buy Tickets</a>
</div>
<div class="performance">
  <h3><a href="/eventperformances.asp?evt=2202">Golden & Gay: 10th Annual Cabaret</a></h3>
  <div>Saturday, November 7, 2026 5:00 PM</div>
  <div>The Triple Door Seattle, WA</div>
  <span>sold out</span>
</div>
"""

class TripleDoorV85Tests(unittest.TestCase):
    def test_accesso_performance_listing(self):
        events = TripleDoorSource.parse_listing(HTML)
        self.assertEqual(len(events), 2)
        titles = {e.title for e in events}
        self.assertIn('Murray Hill "Showbiz! The Tour"', titles)
        self.assertIn("Golden & Gay: 10th Annual Cabaret", titles)
        self.assertNotIn("Dan Rodriguez at The Rabbit Box", titles)
        sold = next(e for e in events if e.title.startswith("Golden"))
        self.assertTrue(sold.sold_out)

if __name__ == "__main__":
    unittest.main()
