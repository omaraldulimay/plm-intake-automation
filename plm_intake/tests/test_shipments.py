import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import shipments as sh  # noqa: E402

ORDER = {"id": "O1", "title": "PO-LIEFERANT_D-AB1", "items": [
    {"name": "AN-43 Leggings", "product": {"id": "P43"}, "variants": [{"name": "Black", "variantId": "V43B", "amounts": [{"key": "S", "quantity": 100}, {"key": "M", "quantity": 200}]},
                                                                      {"name": "Brown", "variantId": "V43R", "amounts": [{"key": "S", "quantity": 50}]}]},
    {"name": "F-2 Fleece", "product": {"id": "PF2"}, "variants": [{"name": "Default Style", "variantId": "VF2", "amounts": [{"key": "ONE SIZE", "quantity": 300}]}]},
    {"name": "Ohne Produkt", "product": None, "variants": []}]}
BYID = {"P43": "AN-43", "PF2": "F-2"}


def doc(**kw):
    d = {"doc_type": "PACKING_LIST", "po_number": "AB1-SEA", "source": {"mail_id": "m1"}, "notes": "shipment by sea, container", "open": [],
         "items": [{"sku": "AN-43", "name": "AN-43 Leggings", "variants": [{"color": "Black", "sizes": {"S": 60, "M": 100}}, {"color": "Brown", "sizes": {"S": 20}}]}]}
    d.update(kw); return d


class AusBelegen(unittest.TestCase):
    def test_packliste_wird_pending_sendung_mit_belegmengen(self):
        c, h = sh.plan_from_docs([("f.json", doc(), "O1")], {"O1": ORDER}, [], BYID)
        self.assertEqual(h, []); s = c[0]
        self.assertEqual((s["status"], s["method"]), ("pending", "sea")); self.assertIn("AB1-SEA", s["title"]); self.assertIn("[doc:m1:AB1-SEA:PACKING_LIST]", s["notes"])
        l = s["products"][0]; self.assertEqual((l["id"], l["orderId"]), ("P43", "O1"))
        self.assertEqual({v["id"]: sum(q["quantityToShip"] for q in v["sizes"]) for v in l["variants"]}, {"V43B": 160, "V43R": 20})

    def test_methode_aus_text(self):
        for txt, m in (("shipment by air AWB 123", "air"), ("Bahn / train 20 Tage", "ground"), ("sea freight container", "sea")):
            self.assertEqual(sh.guess_method(txt)[0], m, txt)
        self.assertEqual(sh.guess_method("nichts"), ("sea", False))

    def test_belegnummer_endung_hat_vorrang_vor_freitext(self):
        for suffix, m in (("AB1-SEA", "sea"), ("AB1-AIR", "air"), ("AB1-TRAIN", "ground"), ("AB1_RAIL", "ground")):
            d = doc(po_number=suffix, notes="enthaelt Wort air und sea und train")
            self.assertEqual(sh.plan_from_docs([("f", d, "O1")], {"O1": ORDER}, [], BYID)[0][0]["method"], m, suffix)
        self.assertIsNone(sh.method_from_ref("AB1")); self.assertIsNone(sh.method_from_ref("SEAWOLF1"))

    def test_verpackungsfreigabe_ist_kein_versandbeleg(self):
        d = doc(notes="Es handelt sich um eine Verpackungs- und Etikettenfreigabe (Polybag-Barcode-Sticker, Exporter-Carton-Marks), keine Rechnung")
        c, h = sh.plan_from_docs([("f", d, "O1")], {"O1": ORDER}, [], BYID); self.assertEqual(c, []); self.assertIn("Freigabe", h[0][1])
        self.assertFalse(sh.is_packaging_doc(doc(notes="Packing list: 520 ctns, gross weight 4950 kg, approval of sizes")))

    def test_idempotent_gleicher_beleg_zweimal_nur_einmal(self):
        c, _ = sh.plan_from_docs([("f.json", doc(), "O1"), ("f.json", doc(), "O1")], {"O1": ORDER}, [], BYID); self.assertEqual(len(c), 1)
        c2, _ = sh.plan_from_docs([("f.json", doc(), "O1")], {"O1": ORDER}, [{"notes": c[0]["notes"], "products": []}], BYID); self.assertEqual(c2, [])

    def test_teilsendungen_je_beleg_eine_sendung(self):
        a = doc(po_number="AB1-SEA"); b = doc(po_number="AB1-AIR", notes="by air"); b["source"] = {"mail_id": "m2"}
        c, _ = sh.plan_from_docs([("a.json", a, "O1"), ("b.json", b, "O1")], {"O1": ORDER}, [], BYID)
        self.assertEqual([x["method"] for x in c], ["sea", "air"])

    def test_menge_ohne_groessenverteilung_nimmt_einzige_ordergroesse(self):
        d = doc(items=[{"sku": "F-2", "name": "F-2 Fleece", "variants": [{"color": None, "sizes": {}, "quantity": 120}]}])
        s = sh.plan_from_docs([("f.json", d, "O1")], {"O1": ORDER}, [], BYID)[0][0]
        self.assertEqual(s["products"][0]["variants"][0]["sizes"], [{"size": "ONE SIZE", "quantityToShip": 120}])

    def test_alles_oder_nichts_fehlende_positionen_verhindern_die_sendung(self):
        c, h = sh.plan_from_docs([("x.json", doc(items=[{"sku": "XX-9", "name": "Fremd", "variants": [{"color": "Red", "sizes": {"M": 1}}]}]), "O1")], {"O1": ORDER}, [], BYID)
        self.assertEqual(c, []); self.assertIn("nicht vollstaendig", h[0][1])
        d = doc(); d["items"].append({"sku": "XX-9", "name": "Fremd", "variants": [{"color": "Red", "sizes": {"M": 1}}]})   # eine Position passt, eine nicht
        c, h = sh.plan_from_docs([("y.json", d, "O1")], {"O1": ORDER}, [], BYID)
        self.assertEqual(c, []); self.assertIn("XX-9", h[0][1])

    def test_groessen_die_die_order_nicht_hat_verhindern_die_sendung(self):
        d = doc(items=[{"sku": "AN-43", "name": "AN-43 Leggings", "variants": [{"color": "Black", "sizes": {"XL": 5}}]}])   # Order hat S und M, kein XL
        c, h = sh.plan_from_docs([("z.json", d, "O1")], {"O1": ORDER}, [], BYID); self.assertEqual(c, []); self.assertIn("nicht in der Order", h[0][1])

    def test_eine_einzige_order_groesse_nimmt_alle_belegmengen_auf(self):
        d = doc(items=[{"sku": "F-2", "name": "F-2 Fleece", "variants": [{"color": None, "sizes": {"S": 3, "M": 4, "L": 5}}]}])
        s = sh.plan_from_docs([("k.json", d, "O1")], {"O1": ORDER}, [], BYID)[0][0]
        self.assertEqual(s["products"][0]["variants"][0]["sizes"], [{"size": "ONE SIZE", "quantityToShip": 12}])

    def test_vorhandene_sammelsendung_verhindert_doppelte_mengen(self):
        gen = {"id": "G", "title": "Sendung PO-LIEFERANT_D-AB1", "notes": "Mengen = PO-Menge. Quelle Logistik", "products": [{"orderId": "O1"}]}
        c, h = sh.plan_from_docs([("f.json", doc(), "O1")], {"O1": ORDER}, [gen], BYID)
        self.assertEqual(c, []); self.assertIn("Sammel-Sendung", h[0][1])

    def test_beleg_ohne_positionen_macht_keine_sendung(self):
        self.assertEqual(sh.plan_from_docs([("e.json", doc(items=[]), "O1")], {"O1": ORDER}, [], BYID), ([], []))


class Farben(unittest.TestCase):
    def test_sprachuebergreifend(self):
        for a, b in (("Schwarz (GT0301-A1)", "Black"), ("Anthrazit (GT0301-B1)", "Anthrazit / Volcanic Ash 19-3912 TCX"), ("Anthracite Forged Iron (Anthrazit 19-3907 TCX)", "Anthrazit 19-3907TCX"),
                     ("Bordeaux", "Wine red (Bordeaux)"), ("Dark blue", "Dunkelblau"), ("Black", "black"), ("Brown", "Braun"), ("Grey Melange", "Grau Melange")):
            self.assertTrue(sh.color_match(a, b), (a, b))

    def test_verschiedene_farben_passen_nicht(self):
        for a, b in (("Black", "Brown"), ("Grey", "Grey Melange"), ("Dark blue", "Blue"), ("Dark green", "Green"), ("Red", "Wine red (Bordeaux)")):
            self.assertFalse(sh.color_match(a, b), (a, b))

    def test_variante_ohne_id_wird_ueber_den_namen_zugeordnet(self):
        o = {"id": "O9", "title": "PO-Z", "items": [{"name": "GT0301 Bag", "product": {"id": "PG"}, "variants": [{"name": "Black", "variantId": None, "amounts": [{"key": "ONE SIZE", "quantity": 10}]}]}]}
        d = {"doc_type": "PACKING_LIST", "po_number": "Z1", "source": {"mail_id": "m"}, "items": [{"sku": "GT0301", "name": "Bag", "variants": [{"color": "Schwarz (GT0301-A1)", "sizes": {}, "quantity": 7}]}]}
        c, h = sh.plan_from_docs([("f", d, "O9")], {"O9": o}, [], {"PG": "GT0301"}); v = c[0]["products"][0]["variants"][0]
        self.assertEqual((v["name"], v["sizes"], "id" in v), ("Black", [{"size": "ONE SIZE", "quantityToShip": 7}], False))


class AusEreignissen(unittest.TestCase):
    S = {"id": "S1", "title": "Sendung X", "status": "pending", "trackingNumber": "", "notes": "", "products": [{"orderId": "O1"}]}

    def ev(self, ms="SHIPPED", trk="", marker="a1"):
        return {"marker": marker, "milestone": ms, "tracking": trk, "mode": "", "text": "B/L erhalten"}

    def test_verladen_setzt_in_transit_und_tracking(self):
        c, u, h = sh.plan_from_events("O1", "PO-X", [self.ev(trk="HBL123")], {"O1": ORDER}, [dict(self.S)])
        self.assertEqual((c, h), ([], [])); self.assertEqual(u[0]["patch"]["status"], "in_transit"); self.assertEqual(u[0]["patch"]["trackingNumber"], "HBL123"); self.assertIn("[ev:a1]", u[0]["patch"]["notes"])

    def test_zwei_ereignisse_zur_selben_sendung_werden_ein_update(self):
        c, u, h = sh.plan_from_events("O1", "PO-X", [self.ev(trk="HBL123", marker="a1"), self.ev(trk="HBL123", marker="b2")], {"O1": ORDER}, [dict(self.S)])
        self.assertEqual(len(u), 1)
        self.assertIn("[ev:a1]", u[0]["patch"]["notes"]); self.assertIn("[ev:b2]", u[0]["patch"]["notes"])   # keine Notiz geht verloren
        self.assertEqual((u[0]["patch"]["status"], u[0]["patch"]["trackingNumber"]), ("in_transit", "HBL123"))

    def test_nie_rueckwaerts(self):
        s = dict(self.S, status="delivered")
        self.assertEqual(sh.plan_from_events("O1", "PO-X", [self.ev()], {"O1": ORDER}, [s])[1], [])
        s2 = dict(self.S, status="in_transit")
        u = sh.plan_from_events("O1", "PO-X", [self.ev("SHIPPED")], {"O1": ORDER}, [s2])[1]; self.assertNotIn("status", u[0]["patch"])

    def test_order_mit_nur_gelieferten_sendungen_macht_keinen_aufwand(self):
        s = dict(self.S, status="delivered")
        self.assertEqual(sh.plan_from_events("O1", "PO-X", [self.ev("SHIPPED")], {"O1": ORDER}, [s]), ([], [], []))

    def test_geliefert_setzt_delivered(self):
        u = sh.plan_from_events("O1", "PO-X", [self.ev("DELIVERED")], {"O1": ORDER}, [dict(self.S, status="in_transit")])[1]; self.assertEqual(u[0]["patch"]["status"], "delivered")

    def test_keine_sendung_dann_wird_aus_order_mengen_angelegt(self):
        c, u, h = sh.plan_from_events("O1", "PO-X", [self.ev(trk="T1")], {"O1": ORDER}, [])
        self.assertEqual(u, []); self.assertEqual((c[0]["status"], c[0]["trackingNumber"]), ("in_transit", "T1")); self.assertIn("Order-Menge", c[0]["notes"])
        self.assertEqual(sum(q["quantityToShip"] for l in c[0]["products"] for v in l["variants"] for q in v["sizes"]), 650)

    def test_mehrere_offene_sendungen_sind_mehrdeutig(self):
        c, u, h = sh.plan_from_events("O1", "PO-X", [self.ev()], {"O1": ORDER}, [dict(self.S), dict(self.S, id="S2")])
        self.assertEqual((c, u), ([], [])); self.assertIn("2 offene", h[0][1])

    def test_transportweg_im_ereignis_macht_mehrere_offene_sendungen_eindeutig(self):
        ships = [dict(self.S, id="S1", method="sea"), dict(self.S, id="S2", method="air"), dict(self.S, id="S3", method="ground")]
        e = dict(self.ev(trk="B/L9"), mode="air")
        c, u, h = sh.plan_from_events("O1", "PO-X", [e], {"O1": ORDER}, ships)
        self.assertEqual((c, h), ([], [])); self.assertEqual((u[0]["id"], u[0]["patch"]["status"], u[0]["patch"]["trackingNumber"]), ("S2", "in_transit", "B/L9"))
        both = [dict(self.S, id="S1", method="sea"), dict(self.S, id="S2", method="sea")]   # zwei See-Sendungen: weiter mehrdeutig
        self.assertIn("2 offene", sh.plan_from_events("O1", "PO-X", [dict(self.ev(), mode="sea")], {"O1": ORDER}, both)[2][0][1])

    def test_marker_verhindert_wiederholung(self):
        s = dict(self.S, notes="x [ev:a1]")
        self.assertEqual(sh.plan_from_events("O1", "PO-X", [self.ev()], {"O1": ORDER}, [s]), ([], [], []))

    def test_tracking_ohne_meilenstein_setzt_nur_leere_nummer(self):
        u = sh.plan_from_events("O1", "PO-X", [self.ev("", "TRK9")], {"O1": ORDER}, [dict(self.S)])[1]; self.assertEqual(sorted(u[0]["patch"]), ["notes", "trackingNumber"])
        self.assertEqual(sh.plan_from_events("O1", "PO-X", [self.ev("", "TRK9")], {"O1": ORDER}, [dict(self.S, trackingNumber="ALT")])[1], [])

    def test_apply_bricht_bei_http_fehler_ab(self):
        calls = []
        def call(m, p, b): calls.append((m, p)); return (500, {})
        with self.assertRaises(RuntimeError): sh.apply([{"title": "t", "marker": "m", "order": "o"}], [], call)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
