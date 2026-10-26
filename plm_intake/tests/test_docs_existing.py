import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import core, docs_existing as de  # noqa: E402


class R:  # minimal Result-Ersatz
    def __init__(self, codes, existing_id=None, decision="BLOCK", msgs=None):
        self.issues = [core.Issue("WARN", c, (msgs or {}).get(c, c)) for c in codes]
        self.existing_id, self.decision = existing_id, decision


class Klassifizierung(unittest.TestCase):
    def test_arten(self):
        self.assertEqual(de.classify("f", {}, R(["delivery_document_only"], "O1"), {})[0], "DELIVERY_DOC")
        self.assertEqual(de.classify("f", {}, R(["delivery_document_only"], None), {})[0], "ORPHAN_DOC")
        self.assertEqual(de.classify("f", {}, R(["exists_changed"], "O1", "UPDATE"), {})[0], "PI_CHANGED")
        self.assertEqual(de.classify("f", {}, R(["duplicate"], "O1", "SKIP"), {})[0], "SKIP")
        self.assertEqual(de.classify("f", {}, R(["style_overlap"], "O1"), {})[0], "REORDER_QUESTION")
        self.assertEqual(de.classify("f", {}, R([], None, "BLOCK"), {})[0], "OTHER_BLOCK")

    def test_overrides(self):
        r = R(["style_overlap"], "O1")
        self.assertEqual(de.classify("f", {}, r, {"f": "NOTE"})[0], "DELIVERY_DOC")
        self.assertEqual(de.classify("f", {}, r, {"f": "SKIP"})[0], "SKIP")


class Ereignis(unittest.TestCase):
    PARENT = {"id": "O1", "title": "PO-LIEFERANT_D-ALI", "poNumber": "LIEFERANT_D-ALI"}

    def test_lieferbeleg_wird_verlaufszeile_ohne_bankdaten_und_ohne_statusaenderung(self):
        po = {"doc_type": "INVOICE", "po_number": "LIEFERANT_D-ALI-SEA", "vendor": "LIEFERANT_D", "currency": "USD", "total_pieces": 100, "total_cost": 1234.5,
              "notes": "Zahlung auf IBAN DE89 3704 0044 0532 0130 00", "source": {"mail_id": "m1"}, "payments": [{"name": "70%", "amount": 864.15, "status": "Unpaid"}]}
        f = de.make_event("x.json", po, "DELIVERY_DOC", self.PARENT, R([]), "2026-10-15 10:00")
        e = f["events"][0]
        self.assertEqual(e["ref"]["po_number"], "LIEFERANT_D-ALI"); self.assertIs(e["details"]["paid"], False); self.assertEqual(e["key"], "doc:x.json:LIEFERANT_D-ALI-SEA:INVOICE")
        self.assertIn("100 Stk", e["summary"]); self.assertEqual(f["mail_id"], "m1")

    def test_neue_pi_fassung_nur_notiz_und_pruefauftrag(self):
        po = {"doc_type": "PI", "po_number": "P1", "source": {"mail_id": "m2"}}
        e = de.make_event("y.json", po, "PI_CHANGED", self.PARENT, R(["exists_changed"], "O1", "UPDATE", {"exists_changed": "anders"}), "t")["events"][0]
        self.assertEqual(e["type"], "ORDER_CHANGE"); self.assertTrue(e["action_needed"]); self.assertIn("NEUE FASSUNG", e["summary"])


class SchwacheZuordnungSchaerfer(unittest.TestCase):
    """Beleg ohne PO-Nr: nur Lieferant/Style darf nicht an eine Order gehen, wenn Menge UND Styles klar abweichen (Lieferant I #96 vs. Rechnungen 422/438)."""
    V = {"id": "VS", "name": "Lieferant I"}
    O96 = {"id": "O96", "orderNumber": 96, "title": "PO-LIEFERANT_I-SPR2026000000409", "poNumber": "SPR2026000000409", "manufacturer": {"id": "VS"}, "totalNumberOfPieces": 10852,
           "items": [{"name": "26246 BAYAN TAYT"}, {"name": "26779 KADIN SWEAT"}, {"name": "26557 KADIN ESOFMAN ALTI"}, {"name": "26585-U KADIN ESOFMAN ALTI"}, {"name": "26701 ERKEK TSHIRT"}, {"name": "26805 BAYAN TAYT"}]}

    def beleg(self, pcs, skus, **kw):
        d = {"doc_type": "INVOICE", "po_number": None, "total_pieces": pcs, "source": {"doc": "SPR-X"}, "items": [{"sku": s, "name": s} for s in skus]}
        d.update(kw); return d

    def test_beispiel_422_menge_1_78x_und_2_von_6_styles_ist_klaerfall(self):
        info = {}
        p, amb = de.parent_for(self.V, self.beleg(19275, ["26246", "26779", "HD210", "26591-U", "26704", "26296"]), [self.O96], {"products": []}, info)
        self.assertIsNone(p); self.assertEqual(amb, []); self.assertIn("1.78x", info["abweichend"][0]); self.assertIn("Style-Ueberdeckung", info["abweichend"][0])

    def test_beispiel_438_menge_unter_0_67x_ist_klaerfall(self):
        p, _ = de.parent_for(self.V, self.beleg(7267, ["26598_O", "26598_U", "26779", "26504", "26592_U", "26557"]), [self.O96], {"products": []}, {})
        self.assertIsNone(p)

    def test_teillieferung_mit_denselben_styles_bleibt_zuordenbar(self):   # Menge 0,5x, aber Styles voll abgedeckt
        p, _ = de.parent_for(self.V, self.beleg(5000, ["26246", "26779", "26557"]), [self.O96], {"products": []}, {})
        self.assertEqual(p["id"], "O96")

    def test_andere_menge_aber_passende_styles_oder_umgekehrt_bleibt_zuordenbar(self):
        self.assertEqual(de.parent_for(self.V, self.beleg(30000, ["26246", "26779"]), [self.O96], {"products": []}, {})[0]["id"], "O96")   # Menge 2,8x, Styles 100 %
        self.assertEqual(de.parent_for(self.V, self.beleg(10500, ["26246", "26779", "HD210", "26591-U"]), [self.O96], {"products": []}, {})[0]["id"], "O96")   # Menge passt, Styles 50 %

    def test_unbekannte_menge_urteilt_nicht(self):
        self.assertEqual(de.parent_for(self.V, self.beleg(None, ["26246", "HD210", "26704"]), [self.O96], {"products": []}, {})[0]["id"], "O96")

    def test_rechnungsnummer_als_po_nr_der_eigenen_order_ist_stark(self):   # neue Order PO-...-422: Beleg landet dort, nicht bei #96
        o98 = {"id": "O98", "orderNumber": 98, "title": "PO-LIEFERANT_I-SPR2026000000422", "poNumber": "SPR2026000000422", "manufacturer": {"id": "VS"}, "totalNumberOfPieces": 19275, "items": [{"name": "26246 BAYAN TAYT"}]}
        p, _ = de.parent_for(self.V, self.beleg(19275, ["26246", "26779", "HD210"], source={"doc": "SPR2026000000422"}), [self.O96, o98], {"products": []}, {})
        self.assertEqual(p["id"], "O98")

    def test_delivery_doc_meldet_klaerfall_statt_zuordnung(self):
        ctx = {"vendors": [self.V], "products": [], "aliases": {}}
        row, _ = de.delivery_doc("x.json", dict(self.beleg(19275, ["26246", "26779", "HD210", "26591-U", "26704", "26296"]), vendor="Lieferant I"), ctx, {"O96": self.O96}, {})
        self.assertEqual(row["kind"], "AMBIGUOUS_DOC"); self.assertIn("weichen klar", row["why"])


class ElternOrder(unittest.TestCase):
    V = {"id": "V1", "name": "LIEFERANT_AA"}
    O = [{"id": "A", "title": "PO-LIEFERANT_AA-26WJD-107-SS26-1ST-ORDER", "manufacturer": {"id": "V1"}, "items": [{"name": "SMI2604 SHORTS"}]},
         {"id": "B", "title": "PO-LIEFERANT_AA-26WJD-108-REORDER", "manufacturer": {"id": "V1"}, "items": [{"name": "SMI2604 SHORTS"}]},
         {"id": "C", "title": "PO-ANDERER-26WJD-107", "manufacturer": {"id": "V2"}, "items": []}]

    def test_vertragsnummer_im_titel_eindeutig(self):
        p, amb = de.parent_for(self.V, {"po_number": "26WJD-107-SMILODOX"}, self.O, {"products": []})
        self.assertEqual(p["id"], "A"); self.assertEqual(amb, [])

    def test_mehrere_kandidaten_ueber_style_sind_mehrdeutig_und_werden_nicht_geraten(self):
        p, amb = de.parent_for(self.V, {"po_number": "LIEFERANT_AA2674", "items": [{"sku": "SMI2604", "name": "MEN'S SHORTS"}]}, self.O, {"products": []})
        self.assertIsNone(p); self.assertEqual(len(amb), 2)

    def test_vertragsnummer_mehrdeutig_aber_styles_entscheiden(self):
        orders = [{"id": "A", "title": "PO-LIEFERANT_AA-26WJD-108-REORDER", "manufacturer": {"id": "V1"}, "items": [{"name": "SMI2604 SHORTS"}]},
                  {"id": "B", "title": "PO-LIEFERANT_AA-26WJD-108-WINTER", "manufacturer": {"id": "V1"}, "items": [{"name": "SMI2612 JACKET"}]}]
        p, amb = de.parent_for(self.V, {"po_number": "26WJD-108", "items": [{"sku": "SMI2612", "name": "JACKET"}]}, orders, {"products": []})
        self.assertEqual((p["id"], amb), ("B", []))
        p, amb = de.parent_for(self.V, {"po_number": "26WJD-108", "items": [{"sku": "SMI9999", "name": "X"}]}, orders, {"products": []})   # kein Style passt: Mensch
        self.assertIsNone(p); self.assertEqual(len(amb), 2)
        p, amb = de.parent_for(self.V, {"po_number": "26WJD-108"}, orders, {"products": []})   # ohne Positionen: Mensch
        self.assertIsNone(p); self.assertEqual(len(amb), 2)

    def test_mehrdeutig_stueckzahl_oder_notiz_entscheidet(self):
        ctx = {"vendors": [self.V], "products": [], "aliases": {}}
        o = [{"id": "A", "title": "PO-LIEFERANT_AA-X", "manufacturer": {"id": "V1"}, "totalNumberOfPieces": 1000, "notes": "", "items": [{"name": "SMI2612 JACKET"}]},
             {"id": "B", "title": "PO-LIEFERANT_AA-Y", "manufacturer": {"id": "V1"}, "totalNumberOfPieces": 2500, "notes": "Zahlung LIEFERANT_AA2674 erhalten", "items": [{"name": "SMI2612 JACKET"}]}]
        orders = {x["id"]: x for x in o}
        base = {"doc_type": "INVOICE", "vendor": "LIEFERANT_AA", "items": [{"sku": "SMI2612", "name": "JACKET"}], "payments": [], "total_cost": 5}
        row, _ = de.delivery_doc("f.json", {**base, "po_number": "LIEFERANT_AA2674", "total_pieces": 100}, ctx, orders, {})   # Nummer steht nur in B
        self.assertEqual((row["kind"], row["pid"]), ("DELIVERY_DOC", "B"))
        row, _ = de.delivery_doc("f.json", {**base, "po_number": "ZZ999999", "total_pieces": 1005}, ctx, orders, {})   # Stueckzahl trifft nur A
        self.assertEqual((row["kind"], row["pid"]), ("DELIVERY_DOC", "A"))
        for oo, pr in zip(o, (13.4, 13.75)):
            oo["items"] = [{"name": "SMI2612 JACKET", "variants": [{"amounts": [{"quantity": 10, "price": pr}]}]}]
        row, _ = de.delivery_doc("f.json", {**base, "po_number": "ZZ999999", "total_pieces": 100, "total_cost": 1375}, ctx, orders, {})   # Stueckpreis 13,75 nur in B
        self.assertEqual((row["kind"], row["pid"]), ("DELIVERY_DOC", "B"))
        for oo in o: oo["items"] = [{"name": "SMI2612 JACKET"}]
        row, _ = de.delivery_doc("f.json", {**base, "po_number": "ZZ999999", "total_pieces": 300}, ctx, orders, {})   # nichts eindeutig: Mensch
        self.assertEqual(row["kind"], "AMBIGUOUS_DOC")

    def test_fremder_lieferant_und_kurze_nummer_geben_nichts(self):
        self.assertEqual(de.parent_for(self.V, {"po_number": "12"}, self.O, {"products": []}), (None, []))

    def test_beleg_trotz_fehlender_ponr_waehrung_summe_wird_zugeordnet(self):
        ctx = {"vendors": [self.V], "products": [], "aliases": {}}
        po = {"doc_type": "PACKING_LIST", "vendor": "LIEFERANT_AA", "po_number": None, "currency": None, "items": [{"sku": "SMI2604", "name": "SHORTS"}], "payments": [], "total_cost": 5}
        orders = {o["id"]: o for o in self.O[:1]}
        row, _ = de.delivery_doc("f.json", po, ctx, orders, {})
        self.assertEqual((row["kind"], row["pid"]), ("DELIVERY_DOC", "A"))


if __name__ == "__main__":
    unittest.main()
