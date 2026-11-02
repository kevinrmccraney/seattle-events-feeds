import unittest
from seattle_feeds.sources.axsvenue import ParamountSource, NeptuneSource, MooreSource, SubstationSource

HTML = """
Tue (Tuesday) Nov (November) 3, 2026 - 7:30 PM Oh, Mary! Paramount Theatre Seattle, Seattle, WA, United States See Event
Tue (Tuesday) Nov (November) 3, 2026 - 7:31 PM Oh, Mary! Parking Paramount Theatre Seattle, Seattle, WA, United States See Event
Sat (Saturday) Nov (November) 14, 2026 - 7:00 PM Ron Funches The Neptune Theatre, Seattle, WA, United States See Event
Sat (Saturday) Nov (November) 14, 2026 - 9:45 PM Ron Funches The Neptune Theatre, Seattle, WA, United States See Event
Fri (Friday) Nov (November) 6, 2026 - 6:30 PM Periphery The Moore Theatre, Seattle, WA, United States See Event
Wed (Wednesday) Nov (November) 4, 2026 - 9:00 PM Cut Copy (DJ Set) Substation, Seattle, WA, United States See Event
Sun (Sunday) Nov (November) 8, 2026 - 9:00 PM Big Freedia (21+ Event) Substation, Seattle, WA, United States See Event
"""

class AXSVenueTests(unittest.TestCase):
    def test_paramount_filters_parking(self):
        e = ParamountSource().parse_listing(HTML)
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0].title, "Oh, Mary!")

    def test_neptune_keeps_same_day_performances(self):
        e = NeptuneSource().parse_listing(HTML)
        self.assertEqual(len(e), 2)
        self.assertEqual({x.start_at.hour for x in e}, {19, 21})

    def test_moore(self):
        e = MooreSource().parse_listing(HTML)
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0].title, "Periphery")

    def test_substation_age(self):
        e = SubstationSource().parse_listing(HTML)
        self.assertEqual(len(e), 2)
        big = next(x for x in e if x.title.startswith("Big Freedia"))
        self.assertEqual(big.age_restriction, "21+")

if __name__ == "__main__":
    unittest.main()
