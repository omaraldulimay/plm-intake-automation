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
