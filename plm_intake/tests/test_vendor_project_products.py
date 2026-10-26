import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import vendor_project_products as vpp, vendor_projects as vp  # noqa: E402


def prod(i, vid, name=None, nv=2, sku=None):
    return {"id": "P%s" % i, "name": name or "Produkt %s" % i, "sku": sku or "S%s" % i, "mainManufacturer": {"id": vid} if vid else None,
            "variants": [{"id": "P%sV%d" % (i, k)} for k in range(nv)]}


VEN = [{"id": "VA", "name": "Alpha Co"}, {"id": "VB", "name": "Beta"}, {"id": "VZ", "name": "ZZ-Test"}]
PRODS = [prod(i, "VA") for i in range(1, 6)] + [prod(10, "VB"), prod(11, "VB", nv=0), prod(12, "VB", name="ZZV-300"), prod(13, "VB", sku="T1-5"),
                                              prod(14, "VZ"), prod(15, None)]


class Plan(unittest.TestCase):
    def test_vendors_needing_project(self):
        self.assertEqual(vpp.vendors_needing_project(VEN, PRODS), {"VA"})

    def test_plan_ohne_projekt(self):
        pl = vpp.plan(VEN, PRODS, [])
        self.assertEqual(pl["adds"], [])
        self.assertEqual([r["status"] for r in pl["rows"]], ["Projekt fehlt (wird angelegt)", "kein Projekt (erst bei erster Order)"])

    def test_plan_nur_fehlende_alle_varianten(self):
        prj = [{"id": "J1", "name": "ALPHA co", "products": [{"productId": "P1"}, {"productId": "P2"}]}, {"id": "J2", "name": "Beta", "products": []}]
        pl = vpp.plan(VEN, PRODS, prj)
        a = {x["project_id"]: x for x in pl["adds"]}
        self.assertEqual([p["productId"] for p in a["J1"]["products"]], ["P3", "P4", "P5"])
        self.assertEqual(a["J1"]["products"][0]["selectedVariants"], ["P3V0", "P3V1"])
        self.assertIsNone(a["J1"]["products"][0]["sourceData"])
        self.assertEqual([p["productId"] for p in a["J2"]["products"]], ["P10"])      # Test-Produkte, ohne Variante, Test-Lieferant ausgelassen
        self.assertTrue(any("ohne Variante" in w for w in pl["warnings"]))

    def test_limit_und_bloecke(self):
        prods = [prod(i, "VA") for i in range(1, 121)]
        prj = [{"id": "J1", "name": "Alpha Co", "products": []}]
        pl = vpp.plan(VEN, prods, prj, limit=100)
        self.assertEqual(sum(len(a["products"]) for a in pl["adds"]), 100)
        self.assertEqual([len(b["products"]) for b in vpp.blocks_of(pl)], [50, 50])
        self.assertEqual(pl["rows"][0]["status"], "offen (Limit)")

    def test_doppelte_projekte(self):
        prj = [{"id": "J1", "name": "Beta", "products": []}, {"id": "J2", "name": "beta", "products": []}]
        pl = vpp.plan(VEN, PRODS, prj)
        self.assertEqual([a for a in pl["adds"] if a["vendor"] == "Beta"], [])

    def test_nie_entfernen_voll(self):
        prj = [{"id": "J1", "name": "Alpha Co", "products": [{"productId": "P%d" % i} for i in range(1, 6)]}]
        self.assertEqual(vpp.plan(VEN, PRODS, prj)["adds"], [])


class Verify(unittest.TestCase):
    def pl(self):
        return vpp.plan(VEN, PRODS, [{"id": "J1", "name": "Alpha Co", "products": [{"productId": "P1"}]}], only_vendor="Alpha Co")

    def test_ok(self):
        pl = self.pl()
        after = [{"id": "J1", "productCount": 5, "products": [{"productId": "P%d" % i} for i in range(1, 6)]}]
        self.assertEqual(vpp.verify(pl, {"after": after, "blocks": [{"project": "J1", "err": None}]}), (4, []))

    def test_doppelt_und_zaehler(self):
        pl = self.pl()
        after = [{"id": "J1", "productCount": 5, "products": [{"productId": "P%d" % i} for i in (1, 2, 3, 4, 4)]}]
        ok, errs = vpp.verify(pl, {"after": after, "blocks": []})
        self.assertEqual(ok, 0); self.assertEqual(len(errs), 1)

    def test_run_dry_und_apply(self):
        calls = []

        def runner(js):
            calls.append(js)
            if "addMultipleProductsToProject" in js:
                return {"blocks": [{"project": "J1", "err": None}], "after": [{"id": "J1", "productCount": 5, "products": [{"productId": "P%d" % i} for i in range(1, 6)]}]}
            return {"projects": [{"id": "J1", "name": "Alpha Co", "products": [{"productId": "P1"}]}]}
        L, res = vpp.run(VEN, PRODS, False, runner=runner)
        self.assertEqual(len(calls), 1)
        self.assertEqual(res["neu"], 0)
        L, res = vpp.run(VEN, PRODS, True, runner=runner, backup_fn=lambda *a: "bk")
        self.assertEqual((res["neu"], res["fehler"]), (4, 0))
        self.assertIn("- Projekt-Produkte: neu 4, Fehler 0", L)


class ProjektRegel(unittest.TestCase):
    def test_projekt_ohne_order_ab_5_produkten(self):
        pl = vp.plan(VEN, [], [], product_vendors=vpp.vendors_needing_project(VEN, PRODS))
        self.assertEqual(pl["create"], ["Alpha Co"])
        self.assertEqual(vp.plan(VEN, [], [])["create"], [])


if __name__ == "__main__":
    unittest.main()


class Sync(unittest.TestCase):
    def test_rauschen_und_echt(self):
        noise = {"changes": {"name": None, "variants": {"stored": {"count": 3}, "current": {"count": 3, "details": ['Variant "A" changed: description changed']}}, "updatedAt": None}}
        self.assertFalse(vpp.real_change(noise))
        self.assertTrue(vpp.real_change({"changes": {"name": {"stored": "a", "current": "b"}}}))
        self.assertTrue(vpp.real_change({"changes": {"variants": {"stored": {"count": 2}, "current": {"count": 3, "details": []}}}}))
        self.assertEqual(vpp.resync({"J": {"outOfSyncCount": 1, "outOfSyncProducts": [dict(noise, linkedProductId="L")]}}, runner=lambda js: 1 / 0), {"resync": []})
