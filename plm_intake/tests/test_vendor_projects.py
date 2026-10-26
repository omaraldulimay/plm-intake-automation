import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import tagesbericht as tb, vendor_projects as vp  # noqa: E402

VEN = [{"id": "VA", "name": "Lieferant AB Pvt Ltd"}, {"id": "VB", "name": "Beta Co., Ltd"}, {"id": "VZ", "name": "ZZ-FULLCASE Vendor"}, {"id": "VC", "name": "Gamma"}]
ORD = [{"id": "O1", "title": "PO-LIEFERANT_AB-1", "manufacturer": {"id": "VA"}},
       {"id": "O2", "title": "PO-BETA-1", "manufacturer": {"id": "VB"}},
       {"id": "O3", "title": "PO-BETA-2", "manufacturer": {"id": "VB"}},
       {"id": "O4", "title": "PO-BETA-T1", "manufacturer": {"id": "VB"}},
       {"id": "O5", "title": "ZZ-X", "manufacturer": {"id": "VB"}},
       {"id": "O6", "title": "PO-ZZFULLCASE-ZZ-AUTO-001", "manufacturer": {"id": "VZ"}},
       {"id": "O7", "title": "PO-OHNE", "manufacturer": None}]
PRJ = [{"id": "P2", "name": "BETA co ltd", "linkedOrders": [{"_id": "L1", "orderId": "O2"}]}]


class Plan(unittest.TestCase):
    def test_test_titel(self):
        for t in ("ZZ-X", "PO-A-T1", "PO-A-T1-2", "Mein TEST", "PO-ZZFULLCASE-1"):
            self.assertTrue(vp.is_test(t), t)
        self.assertFalse(vp.is_test("PO-LIEFERANT_AB-1"))

    def test_plan(self):
        pl = vp.plan(VEN, ORD, PRJ)
        self.assertEqual(pl["create"], ["Lieferant AB Pvt Ltd"])           # Beta hat Projekt (normalisiert), Gamma/ZZ keine echten Orders
        self.assertEqual(pl["vendors_ohne_projekt"], ["Lieferant AB Pvt Ltd"])
        self.assertEqual([(l["order_id"], l["project_id"]) for l in pl["links"]], [("O1", None), ("O3", "P2")])   # O2 schon verknuepft: unberuehrt
        self.assertEqual(pl["no_vendor"], ["PO-OHNE"])
        self.assertTrue(any("ohne erkennbaren Lieferanten" in w for w in pl["warnings"]))

    def test_order_nie_in_zweitem_projekt(self):
        prj = [{"id": "PX", "name": "Anderes", "linkedOrders": [{"_id": "L", "orderId": "O3"}]}] + PRJ
        pl = vp.plan(VEN, ORD, prj)
        self.assertNotIn("O3", [l["order_id"] for l in pl["links"]])

    def test_doppelte_projekte_nichts_raten(self):
        prj = PRJ + [{"id": "P3", "name": "Beta Co Ltd", "linkedOrders": []}]
        pl = vp.plan(VEN, [ORD[2]], prj)
        self.assertEqual(pl["links"], [])
        self.assertTrue(any("Mehrere Projekte" in w for w in pl["warnings"]))

    def test_limit(self):
        orders = [{"id": "X%d" % i, "title": "PO-B-%d" % i, "manufacturer": {"id": "VB"}} for i in range(40)]
        pl = vp.plan(VEN, orders, PRJ, max_links=30)
        self.assertEqual(len(pl["links"]), 30)
        self.assertTrue(any("naechsten Lauf" in w for w in pl["warnings"]))


class Lauf(unittest.TestCase):
    def runner(self, written):
        def r(js):
            if js == vp.JS_READ:
                return {"projects": [dict(p) for p in PRJ]}
            written.append(js)
            return {"created": [{"name": "Lieferant AB Pvt Ltd", "id": "P1"}], "links": [{"order": "O1", "project": "P1", "err": None}, {"order": "O3", "project": "P2", "err": None}],
                    "after": [{"id": "P1", "name": "Lieferant AB Pvt Ltd", "linkedOrders": [{"orderId": "O1"}]}, {"id": "P2", "name": "Beta Co., Ltd", "linkedOrders": [{"orderId": "O2"}, {"orderId": "O3"}]}]}
        return r

    def test_trockenlauf_schreibt_nichts(self):
        w = []
        L, res = vp.run(VEN, ORD, False, runner=self.runner(w))
        self.assertEqual(w, []); self.assertEqual(res["neu"], 0)

    def test_apply_zuruecklesen(self):
        w, bk = [], []
        L, res = vp.run(VEN, ORD, True, runner=self.runner(w), backup_fn=lambda p, pl: bk.append(p) or "bk")
        self.assertEqual((res["neu"], res["verknuepft"], res["fehler"]), (1, 2, 0))
        self.assertEqual(len(bk), 1); self.assertIn('"Lieferant AB Pvt Ltd"', w[0])

    def test_zuruecklesen_fehlt(self):
        def r(js):
            if js == vp.JS_READ:
                return {"projects": []}
            return {"created": [], "links": [{"order": "O3", "err": None}], "after": []}
        L, res = vp.run(VEN, [ORD[2]], True, runner=r, backup_fn=lambda p, pl: "bk")
        self.assertEqual((res["verknuepft"], res["fehler"]), (0, 1))
        self.assertTrue(any("Projekte/Verknuepfung" in x for x in res["warnungen"]))


class Bericht(unittest.TestCase):
    def test_zeile(self):
        import datetime as dt
        f = {"zahlen": {}, "klaer_rows": [], "warnungen": [], "projekte": {"neu": 1, "verknuepft": 2, "fehler": 3}}
        txt = tb.build(f, 0, "apply", "", dt.datetime(2026, 10, 20, 8, 30), {"tage": {}, "gesehen": []}, 60)
        self.assertIn("Projekte: neu 1, verknuepft 2, Fehler 3", txt)


if __name__ == "__main__":
    unittest.main()
