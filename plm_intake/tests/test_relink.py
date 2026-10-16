import copy
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import relink  # noqa: E402

PRODUCTS = [{"id": "P6", "sku": "XW26-006", "sizes": ["S", "M", "L"], "variants": [{"id": "P6B", "name": "Black"}, {"id": "P6N", "name": "Navy"}]},
            {"id": "P8", "sku": "XW26-008", "sizes": ["ONE SIZE"], "variants": [{"id": "P8B", "name": "Black"}]}]


def order(items):
    return {"id": "O1", "title": "PO-T", "orderNumber": 5, "items": items}


def it(name, variants, product=None):
    d = {"name": name, "variants": [{"name": n, "amounts": [{"key": k, "quantity": 1, "price": 1, "cost": 1} for k in ks]} for n, ks in variants]}
    if product: d["product"] = {"id": product}
    return d


class Plan(unittest.TestCase):
    def test_sku_aus_positionsname(self):
        for n, e in [("XW26-006 Men T Shirt (crinkle)", "XW26-006"), ("XW-041 Men Windbreaker", "XW-041"), ("SMI2601 Jacket", "SMI2601"), ("Leo Socken", None)]:
            self.assertEqual(relink.item_sku(n), e, n)

    def test_verknuepft_und_ordnet_farben_zu(self):
        p = relink.plan([order([it("XW26-006 Men T Shirt", [("Black", ["S", "M"]), ("Navy", ["L"])])])], PRODUCTS)
        self.assertEqual(p[0]["links"][0]["product"], "P6")
        self.assertEqual(p[0]["links"][0]["variants"], {"Black": "P6B", "Navy": "P6N"})

    def test_bereits_verknuepfte_positionen_bleiben_unangetastet(self):
        self.assertEqual(relink.plan([order([it("XW26-006 Men T Shirt", [("Black", ["S"])], product="X")])], PRODUCTS), [])

    def test_unbekanntes_produkt_wird_ignoriert(self):
        self.assertEqual(relink.plan([order([it("ZZ-999 Foo", [("Black", ["S"])])])], PRODUCTS), [])

    def test_unbekannte_farbe_oder_groesse_ueberspringt_die_position_komplett(self):
        p = relink.plan([order([it("XW26-006 T", [("Pink", ["S"])]), it("XW26-008 T", [("Black", ["S"])])])], PRODUCTS)
        self.assertEqual(p[0]["links"], [])
        self.assertEqual(len(p[0]["skipped"]), 2)
        self.assertIn("Farbe 'Pink'", p[0]["skipped"][0]["reasons"][0])
        self.assertIn("Groessen", p[0]["skipped"][1]["reasons"][0])

    def test_teilweise_verknuepfung_nur_der_passenden_positionen(self):
        p = relink.plan([order([it("XW26-006 T", [("Black", ["S"])]), it("XW26-008 T", [("Black", ["S"])])])], PRODUCTS)
        self.assertEqual([l["index"] for l in p[0]["links"]], [0])
        self.assertEqual(len(p[0]["skipped"]), 1)


@unittest.skipUnless(shutil.which("node"), "node fehlt")
class Skript(unittest.TestCase):
    ORDER = {"id": "O1", "title": "PO-T", "totalCost": 3, "totalNumberOfPieces": 3, "manufacturer": {"id": "V"},
             "items": [{"name": "XW26-006 T", "product": None, "variants": [{"name": "Black", "variantId": None, "amounts": [{"key": "S", "quantity": 3, "price": 1, "cost": 3}]}]}],
             "payments": [{"name": "p", "status": "Unpaid", "amount": 3, "dueDate": 1}]}
    PLAN = [{"id": "O1", "title": "PO-T", "orderNumber": 5, "skipped": [], "links": [{"index": 0, "name": "XW26-006 T", "product": "P6", "sku": "XW26-006", "variants": {"Black": "P6B"}}]}]

    def run_js(self, mock):
        js = relink.make_js(self.PLAN)
        h = "globalThis.window={}; const STATE=%s; %s\n(%s).then(r=>console.log(JSON.stringify(r)))" % (json.dumps(self.ORDER), mock, js)
        o = subprocess.run(["node", "-e", h], capture_output=True, text=True, timeout=30)
        self.assertEqual(o.returncode, 0, o.stderr)
        return json.loads(o.stdout.strip().splitlines()[-1])

    GOOD = """window.__fetchOrder = async id => ({d: JSON.parse(JSON.stringify(STATE)), e: []});
      window.__updOrder = async (id, patch) => { patch.items.forEach((i, n) => { STATE.items[n].product = i.product ? {id: i.product} : null;
        STATE.items[n].variants.forEach((v, k) => v.variantId = i.variants[k].variantId); }); return {err: [], data: {}}; };"""

    def test_erfolg_daten_unveraendert_links_gesetzt(self):
        r = self.run_js(self.GOOD)[0]
        self.assertTrue(r["dataUnchanged"] and r["linksOk"] and r["otherLinksKept"], r)

    def test_abbruch_wenn_update_menge_veraendert(self):
        mock = self.GOOD.replace("return {err: [], data: {}};", "STATE.items[0].variants[0].amounts[0].quantity = 99; return {err: [], data: {}};")
        r = self.run_js(mock)[0]
        self.assertFalse(r["dataUnchanged"])
        self.assertIn("ABBRUCH", r)

    def test_abbruch_wenn_link_nicht_gespeichert(self):
        mock = self.GOOD.replace("STATE.items[n].product = i.product ? {id: i.product} : null;", "")
        r = self.run_js(mock)[0]
        self.assertFalse(r["linksOk"])
        self.assertIn("ABBRUCH", r)

    def test_abbruch_wenn_position_inzwischen_geaendert(self):
        mock = "STATE.items[0].name = 'ANDERS';" + self.GOOD
        r = self.run_js(mock)[0]
        self.assertIn("geaendert", r["error"])

    def test_abbruch_wenn_schon_verknuepft(self):
        mock = "STATE.items[0].product = {id: 'X'};" + self.GOOD
        self.assertIn("verknuepft", self.run_js(mock)[0]["error"])

    def test_helfer_fehlen(self):
        self.assertIn("fatal", self.run_js("")[0])

    def test_updorder_fehler_stoppt_und_meldet_unsicher(self):
        mock = "window.__fetchOrder = async id => ({d: JSON.parse(JSON.stringify(STATE)), e: []}); window.__updOrder = async () => ({err: ['kaputt']});"
        r = self.run_js(mock)[0]
        self.assertTrue(r["unsure"])


if __name__ == "__main__":
    unittest.main()
