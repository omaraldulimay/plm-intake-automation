import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import invoice_pos  # noqa: E402


class OhnePreis(unittest.TestCase):
    def test_bestellung_ohne_preis_wird_trotzdem_als_inbox_datei_erzeugt(self):
        with tempfile.TemporaryDirectory() as d:
            p2 = Path(d); (p2 / "x" / "extract").mkdir(parents=True)
            for fid, price in (("att_ok", 4.5), ("att_null", None), ("att_zero", 0)):
                doc = {"order": {"currency": "USD", "po_date": "2026-06-25", "items": [{"style": "S1", "color": "black", "sizes": {"M": 10}, "qty": 10, "price": price}]}}
                (p2 / "x" / "extract" / (fid + ".json")).write_text(json.dumps(doc))
            jobs = [("x", "att_ok", "V", "PO-OK", "n"), ("x", "att_null", "V", "PO-NULL", "n"), ("x", "att_zero", "V", "PO-ZERO", "n")]
            with mock.patch.object(invoice_pos, "P2", p2), mock.patch.object(invoice_pos, "OUT", p2 / "B11" / "inbox"), mock.patch.object(invoice_pos, "JOBS", jobs):
                invoice_pos.main()
            self.assertEqual(sorted(f.name for f in (p2 / "B11" / "inbox").glob("*.json")), ["PO-NULL.json", "PO-OK.json", "PO-ZERO.json"])
            z = json.loads((p2 / "B11" / "inbox" / "PO-ZERO.json").read_text())
            self.assertEqual(z["total_cost"], 0); self.assertEqual(z["items"][0]["variants"][0]["price"], 0.0)
            self.assertNotIn("Preis fehlt im Beleg", z["notes"])   # kein fest eingetragener Text: die Notiz 'PREIS AUSSTEHEND' setzt core.build
            self.assertFalse((p2 / "B11" / "klaerfaelle_preis.md").exists())


class LieferantITeillieferung(unittest.TestCase):
    BELEG = {"doc_type": "INVOICE", "source": {"doc": "SPR1", "mail_id": "m", "mail_date": "2026-10-20 17:17"}, "currency": "EUR", "doc_date": "2026-10-20", "incoterm": "FOB", "ship_to": "HH",
             "items": [{"sku": "26246", "name": "BAYAN TAYT 26246", "variants": [{"price": 4.4, "quantity": 30}]}, {"sku": "26704", "name": "ERKEK TSHIRT 26704", "variants": [{"price": 4.5, "quantity": 20}]}],
             "total_pieces": 50, "total_cost": 222.0}
    PL = {"26246|SCHWARZ": {"XS": 10, "M": 20}, "26704|WEIB": {"S": 5}, "26704|SCHWARZ": {"S": 5, "M": 10}}

    def test_doc_aus_beleg_und_packliste(self):
        d = invoice_pos.lieferant_i_doc(self.BELEG, self.PL, 10, "m")
        self.assertEqual((d["po_number"], d["total_pieces"], d["total_cost"], d["doc_type"]), ("SPR1", 50, 222.0, "PO"))
        cols = {v["color"]: v["sizes"] for it in d["items"] for v in it["variants"]}
        self.assertEqual(cols["Weiß"], {"S": 5}); self.assertEqual(cols["Schwarz"] in ({"XS": 10, "M": 20}, {"S": 5, "M": 10}), True)
        self.assertIn("Teillieferung zu Lieferant I-Bestellung 409", d["notes"]); self.assertEqual(d["payments"][0]["amount"], 222.0)

    def test_stueckzahl_oder_betrag_passt_nicht_gegen_den_beleg_dann_keine_order(self):
        with self.assertRaises(ValueError):
            invoice_pos.lieferant_i_doc(self.BELEG, {**self.PL, "26246|SCHWARZ": {"XS": 10, "M": 19}}, 10, "m")   # Style-Menge laut Packliste 29 != 30
        with self.assertRaises(ValueError):
            invoice_pos.lieferant_i_doc(dict(self.BELEG, total_cost=300.0), self.PL, 10, "m")

    def test_core_build_legt_eigene_order_an_trotz_style_ueberschneidung(self):
        from plm_intake import core
        ctx = {"vendors": [{"id": "VS", "name": "Lieferant I"}], "products": [], "aliases": {},
               "orders": [{"id": "O96", "orderNumber": 96, "title": "PO-LIEFERANT_I-SPR0409", "poNumber": "SPR0409", "manufacturer": {"id": "VS"}, "totalNumberOfPieces": 100, "totalCost": 1.0, "items": [{"name": "26246 X"}]}]}
        r = core.build(invoice_pos.lieferant_i_doc(self.BELEG, self.PL, 10, "m"), ctx, force_create=True)
        self.assertEqual(r.decision, "CREATE"); self.assertEqual(r.payload["title"], "PO-LIEFERANT_I-SPR1")
        p = invoice_pos.lieferant_i_payload(r)
        self.assertNotIn("dueDate", p["payments"][0]); self.assertNotIn("Platzhalter", p["notes"])


if __name__ == "__main__":
    unittest.main()
