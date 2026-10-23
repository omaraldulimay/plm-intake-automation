import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import docs_existing as de, price_fill as pf  # noqa: E402


def order(oid="O1", price=0, qtys=(("S", 100), ("M", 200)), name="SXW26-011 Hose", color="Black", title="PO-LIEFERANT_E-A"):
    return {"id": oid, "title": title, "orderNumber": 7, "manufacturer": {"id": "V1"}, "totalNumberOfPieces": sum(q for _, q in qtys),
            "items": [{"name": name, "variants": [{"name": color, "amounts": [{"key": k, "quantity": q, "price": price, "cost": price * q} for k, q in qtys]}]}]}


def beleg(price=3.6, qty=300, sku="SXW26-011", color="Black", doc_type="INVOICE"):
    return {"doc_type": doc_type, "po_number": "INV-1", "vendor": "Lieferant E", "items": [{"sku": sku, "name": "Hose", "variants": [{"color": color, "price": price, "sizes": {"S": qty // 3, "M": qty - qty // 3}}]}]}


class Plan(unittest.TestCase):
    def test_preis_wird_nachgetragen_bei_passender_position(self):
        r = pf.plan({"O1": order()}, [("rechnung.json", "O1", beleg())], today="2026-10-23 09:00")
        self.assertEqual(len(r["patches"]), 1); self.assertEqual(r["klaer"], []); self.assertEqual(r["konflikte"], [])
        p = r["patches"][0]
        self.assertEqual(p["cells"], [{"item": 0, "variant": 0, "iname": "SXW26-011 Hose", "vname": "Black", "qty": 300.0, "price": 3.6}])
        self.assertIn("PREIS NACHGETRAGEN aus rechnung.json", p["text"]); self.assertIn("pf:" + p["marker"], p["text"])

    def test_menge_innerhalb_toleranz_ja_ausserhalb_klaerfall(self):
        self.assertEqual(len(pf.plan({"O1": order()}, [("a", "O1", beleg(qty=303))])["patches"]), 1)   # +1 %
        r = pf.plan({"O1": order()}, [("a", "O1", beleg(qty=320))])   # +6,7 %
        self.assertEqual(r["patches"], [])
        self.assertEqual(len(r["klaer"]), 1); self.assertIn("Preis-Nachtrag passt nicht", r["klaer"][0]["why"])

    def test_andere_farbe_klaerfall_anderer_style_ignoriert(self):
        r = pf.plan({"O1": order()}, [("a", "O1", beleg(color="Navy"))])
        self.assertEqual(r["patches"], []); self.assertEqual(len(r["klaer"]), 1)
        r = pf.plan({"O1": order()}, [("a", "O1", beleg(sku="XY99-001"))])
        self.assertEqual((r["patches"], r["klaer"]), ([], []))

    def test_vorhandener_preis_wird_nie_ueberschrieben(self):
        r = pf.plan({"O1": order(price=5.0)}, [("a", "O1", beleg(price=3.6))])
        self.assertEqual((r["patches"], r["klaer"]), ([], []))   # keine Position mit Preis 0 -> nichts zu tun
        o = order(price=0); o["items"][0]["variants"].append({"name": "Navy", "amounts": [{"key": "S", "quantity": 50, "price": 5.0, "cost": 250}]})
        b = beleg(price=3.6); b["items"][0]["variants"].append({"color": "Navy", "price": 3.6, "sizes": {"S": 50}})
        r = pf.plan({"O1": o}, [("a", "O1", b)])
        self.assertEqual([c["vname"] for c in r["patches"][0]["cells"]], ["Black"])   # Navy (Preis 5,0) bleibt
        self.assertEqual(len(r["konflikte"]), 1); self.assertIn("UNSTIMMIG", r["konflikte"][0]["why"])

    def test_beleg_ohne_preis_aendert_nichts(self):
        r = pf.plan({"O1": order()}, [("a", "O1", beleg(price=0))])
        self.assertEqual((r["patches"], r["klaer"]), ([], []))

    def test_einzige_variante_ohne_farbe(self):
        r = pf.plan({"O1": order(color="Default Style")}, [("a", "O1", beleg(color=None))])
        self.assertEqual(len(r["patches"]), 1)

    def test_js_dry_ist_standard_und_schreibt_nur_ohne_dry(self):
        r = pf.plan({"O1": order()}, [("a", "O1", beleg())])
        self.assertIn("const DRY = true;", pf.make_js(r)); self.assertIn("const DRY = false;", pf.make_js(r, dry=False))
        self.assertIn("nicht ueberschrieben", pf.make_js(r))


class DocsExisting(unittest.TestCase):
    def test_run_liefert_preis_plan_und_klaerfall_zeilen(self):
        o = order()
        ctx = {"vendors": [{"id": "V1", "name": "Lieferant E"}], "products": [], "orders": [o], "aliases": {}}
        with tempfile.TemporaryDirectory() as d:
            inbox = Path(d) / "in"; inbox.mkdir()
            (inbox / "ok.json").write_text(json.dumps(beleg()))
            b2 = beleg(color="Navy"); b2["po_number"] = "INV-2"
            (inbox / "nok.json").write_text(json.dumps(b2))
            plans = []
            rows, evs = de.run(inbox, ctx, {}, Path(d) / "out", price_plan=plans)
        self.assertEqual({r["kind"] for r in rows if r["file"] in ("ok.json", "nok.json")} - {"PREIS_KLAERFALL"}, {"DELIVERY_DOC"})
        self.assertEqual([p["file"] for p in plans[0]["patches"]], ["ok.json"])
        kl = [r for r in rows if r["kind"] == "PREIS_KLAERFALL"]
        self.assertEqual([r["file"] for r in kl], ["nok.json"]); self.assertIn("Preis-Nachtrag passt nicht", kl[0]["why"])


if __name__ == "__main__":
    unittest.main()
