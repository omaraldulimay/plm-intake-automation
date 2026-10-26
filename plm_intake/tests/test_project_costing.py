import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import project_costing as pc  # noqa: E402


def order(t, items, total=0):
    return {"title": t, "manufacturer": {"id": "V1"}, "totalCost": total, "items": items}


def item(pid, vid, qtys, price):
    return {"name": "N" + pid, "product": {"id": pid}, "variants": [{"variantId": vid, "name": vid, "amounts": [{"quantity": q, "price": price} for q in qtys]}]}


PRJ = [{"id": "J1", "name": "Alpha", "products": [{"productId": "P1", "selectedVariants": ["A", "B"]}]}]
VEN = [{"id": "V1", "name": "Alpha"}]


class T(unittest.TestCase):
    def test_summe_und_konflikt(self):
        o = [order("O1", [item("P1", "A", [1, 2], 5), item("P1", "B", [4], 2)], 100), order("O2", [item("P1", "A", [3], 5), item("P1", "B", [1], 3), item("P9", "X", [1], 1)])]
        p = pc.plan(VEN, o, PRJ)["projekte"][0]
        self.assertEqual([(r["variantId"], r["menge"], r["preis"]) for r in p["zeilen"]], [("A", 6, 5.0)])
        self.assertEqual(p["konflikte"][0]["preise"], [2.0, 3.0])
        self.assertEqual(p["summe"], 30.0)
        self.assertEqual(len(p["fremd"]), 1)
        self.assertIn("Alpha", pc.report({"projekte": [p]}))

    def test_test_order_ignoriert(self):
        o = [order("ZZ-1", [item("P1", "A", [1], 5)])]
        self.assertEqual(pc.plan(VEN, o, PRJ)["projekte"], [])


if __name__ == "__main__":
    unittest.main()


class BuildJobsTest(unittest.TestCase):
    def test_vorhandene_werte_bleiben(self):
        from plm_intake import project_costing as pc
        proj = {"zeilen": [{"variantId": "a", "produkt": "P", "variante": "V", "menge": 10, "preis": 2.0},
                           {"variantId": "b", "produkt": "P", "variante": "W", "menge": 5, "preis": 3.0}]}
        costing = {"variants": [{"variantId": "a", "projectProductId": "pp", "quantity": 10, "buyingPrice": 0},
                                {"variantId": "b", "projectProductId": "pp", "quantity": 7, "buyingPrice": 0}]}
        jobs, skip = pc.build_jobs(proj, costing)
        self.assertEqual([(j["variantId"], j["qty"], j["price"]) for j in jobs], [("a", None, 2.0), ("b", None, 3.0)])
        self.assertEqual(len(skip), 1)
        self.assertEqual(pc.costing_sum(costing), 0.0)
