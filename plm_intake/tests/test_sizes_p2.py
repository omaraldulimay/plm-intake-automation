import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import sizes_p2 as sz  # noqa: E402

P = lambda *s: {"sizes": [{"title": x} for x in s]}
PL = [{"size": "3XL", "ean": "4006381333931", "variation_no": "X-A6"}]


class Plan(unittest.TestCase):
    def test_add_nach_xxl(self):
        r = sz.plan(P("S", "M", "XL", "XXL"), PL)
        self.assertEqual((r["action"], r["afterSize"]), ("add", "XXL"))

    def test_schreibweise_2xl(self):
        self.assertEqual(sz.plan(P("S", "2XL"), PL)["afterSize"], "2XL")

    def test_vorhanden_andere_schreibweise_keine_dublette(self):
        r = sz.plan(P("S", "XXL", "3XXL"), PL)
        self.assertEqual(r["action"], "skip"); self.assertIn("3XXL", r["reason"])

    def test_ohne_plenty_3xl(self):
        self.assertEqual(sz.plan(P("S", "XXL"), [{"size": "XXL", "ean": "4006381333931"}])["action"], "skip")

    def test_mehrdeutig(self):
        self.assertEqual(sz.plan(P("S", "XXL"), PL, 2)["action"], "skip")


if __name__ == "__main__":
    unittest.main()
