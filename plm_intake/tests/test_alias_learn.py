import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import alias_learn, docs_existing, events  # noqa: E402

V = [{"id": "VA", "name": "Lieferant A"}]
O = [{"id": "A1", "title": "PO-ALPHA-1", "poNumber": "", "manufacturer": {"id": "VA"}, "status": {"status": "In Production"}, "items": [{"name": "AL29008 Hoodie"}]},
     {"id": "A2", "title": "PO-ALPHA-2", "poNumber": "", "manufacturer": {"id": "VA"}, "status": {"status": "In Production"}, "items": [{"name": "AL30001 Pant"}]}]


def ev(po="PO-ALPHA-1", **det):
    return {"type": "SHIPMENT", "vendor": "Lieferant A", "ref": {"po_number": po, "style": None, "container": None}, "summary": "x", "details": det,
            "_mail": {"id": "m", "date": "2026-10-15 10:00"}}


class Lernen(unittest.TestCase):
    def plan(self, e, aliases=None):
        return events.plan([e], O, V, aliases, vendor_only=True)

    def test_lernt_bei_starkem_signal(self):
        pl = self.plan(ev(invoice_number="LIEFERANT_AA2674", container="MSKU1234567"))
        _, new, conf = alias_learn.learn({}, pl["assigned"], [], O)
        self.assertEqual({k: o for k, o, _ in new}, {"LIEFERANT_AA2674": "A1", "MSKU1234567": "A1"}); self.assertFalse(conf)

    def test_schwaches_signal_lernt_nicht(self):
        e = ev(po=None, invoice_number="LIEFERANT_AA2674")   # nur ueber Lieferant (vendor_only)
        pl = self.plan(e)
        self.assertEqual(alias_learn.learn({}, pl["assigned"], [], O)[1], [])

    def test_konflikt_setzt_mehrdeutig(self):
        al = {"LIEFERANT_AA2674": "A2"}
        pl = self.plan(ev(invoice_number="LIEFERANT_AA2674"))
        res, new, conf = alias_learn.learn(al, pl["assigned"], [], O, apply=True)
        self.assertEqual(conf, [("LIEFERANT_AA2674", "PO-ALPHA-2", "PO-ALPHA-1")])
        self.assertEqual(al["LIEFERANT_AA2674"], alias_learn.AMBIG)

    def test_spaetere_mail_nutzt_alias(self):
        e = ev(po="SPR2026000000409")
        o, why = events.find_order(e, O, V, {"SPR2026000000409": "A2"})
        self.assertEqual((o["id"], why), ("A2", "alias"))
        e2 = ev(po=None, invoice_number="LIEFERANT_AA2674")   # auch ueber Rechnungsnr statt PO
        self.assertEqual(events.find_order(e2, O, V, {"LIEFERANT_AA2674": "PO-ALPHA-1"})[0]["id"], "A1")
        self.assertIsNone(events.find_order(e, O, V, {"SPR2026000000409": alias_learn.AMBIG})[0])   # mehrdeutig wird nie benutzt

    def test_datum_style_menge_nicht_gelernt(self):
        pl = self.plan(ev(invoice_number="2026-10-15", bl="AL29008", awb="85.290", container="12345"))
        keys = [k for k, _, _ in alias_learn.learn({}, pl["assigned"], [], O)[1]]
        self.assertEqual(keys, ["12345"])   # 5 Stellen, kein Datum/Style/Menge; zu kurz (<5) faellt ebenfalls raus
        self.assertFalse(alias_learn.valid("AB12", O[0]))

    def test_trockenlauf_lernt_nichts(self):
        al = {}
        pl = self.plan(ev(invoice_number="LIEFERANT_AA2674"))
        work, new, _ = alias_learn.learn(al, pl["assigned"], [], O, apply=False)
        self.assertEqual(al, {}); self.assertTrue(new and "LIEFERANT_AA2674" in work)

    def test_beleg_nutzt_alias_in_parent_for(self):
        ctx = {"po_aliases": {"LIEFERANT_AA2674": "A2"}, "products": []}
        p, amb = docs_existing.parent_for(V[0], {"po_number": "LIEFERANT_AA2674"}, O, ctx)
        self.assertEqual(p["id"], "A2")

    def test_dokumentnummer_source_doc_zaehlt_als_kennung(self):
        ctx = {"po_aliases": {"LIEFERANT_AA2674": "A2"}, "products": []}
        p, _ = docs_existing.parent_for(V[0], {"po_number": None, "source": {"doc": "LIEFERANT_AA-2674"}}, O, ctx)
        self.assertEqual(p["id"], "A2")
        p, _ = docs_existing.parent_for(V[0], {"po_number": None, "source": {"doc": "LIEFERANT_AA2675"}}, O, ctx)
        self.assertIsNone(p)

    def test_beleg_delivery_doc_lernt(self):
        rows = [{"kind": "DELIVERY_DOC", "pid": "A1", "doc": {"po_number": "AK/625/26"}}]
        self.assertEqual([(k, o) for k, o, _ in alias_learn.learn({}, [], rows, O)[1]], [("AK/625/26", "A1")])


if __name__ == "__main__":
    unittest.main()
