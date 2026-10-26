import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import content_backtest, content_match, events  # noqa: E402

V = [{"id": "VA", "name": "Lieferant A"}]


def order(i, title, items, total, notes=""):
    return {"id": i, "title": title, "manufacturer": {"id": "VA"}, "status": {"status": "In Production"}, "totalNumberOfPieces": total, "_notes": notes,
            "items": [{"name": n, "product": {"id": "P" + n[:4]}, "variants": [{"name": "Black", "amounts": [{"key": "M", "quantity": q}]}]} for n, q in items]}


O = [order("O1", "PO-ALPHA-SWEAT-PROGRAM-1", [("26069 Dawson Hoodie Fleece", 8000)], 8000),
     order("O2", "PO-ALPHA-KUNDE_X-DE-1", [("561873 Seamless Legging", 5000)], 5000),
     order("O3", "PO-ALPHA-KUNDE_X-CH-1", [("561873 Seamless Legging", 1000)], 1000),
     order("O4", "PO-ALPHA-KUNDE_X-LAGER-1", [("561873 Seamless Legging", 540)], 540)]
P = [{"id": "P" + n, "sku": s, "name": nm} for n, s, nm in (("2606", "26069", "Dawson Hoodie"), ("5618", "561873", "Seamless Legging"))]


def ev(summary, **kw):
    e = {"type": "SCHEDULE", "vendor": "Lieferant A", "ref": {"po_number": None, "style": None, "container": None}, "summary": summary, "details": {}, "confidence": 0.9,
         "_mail": {"id": "m1", "date": "2026-10-15 10:00", "subject": "Status"}}
    e.update(kw); return e


class Schalter(unittest.TestCase):
    def find(self, e, flag):
        idx = events.order_index(O, P)
        with mock.patch.dict(os.environ, {"CONTENT_MATCH": flag} if flag else {}, clear=False):
            if not flag:
                os.environ.pop("CONTENT_MATCH", None)
            return events.find_order(e, O, V, None, None, True, idx, None)

    def test_standard_aus(self):
        o, why = self.find(ev("Dawson Fleece ex-factory moved to 20.10."), "")
        self.assertIsNone(o); self.assertTrue(why.startswith("mehrdeutig"))

    def test_an_ordnet_zu_mit_beleg(self):
        e = ev("Dawson Fleece ex-factory moved to 20.10.")
        o, why = self.find(e, "1")
        self.assertEqual((o["id"], why), ("O1", "inhalt"))
        self.assertIn("dawson", e["_content_hit"])
        self.assertIsNone(self.find(ev("Dawson ex-factory moved to 20.10."), "1")[0])   # nur ein unterscheidendes Wort: zu wenig

    def test_kunde_x_bei_mehreren_kunde_x_orders_zaehlt_nicht(self):
        o, why = self.find(ev("KUNDE_X program schedule confirmed, ex-factory 20.10."), "1")
        self.assertIsNone(o)

    def test_lieferantenname_zaehlt_nicht(self):
        self.assertIsNone(self.find(ev("Lieferant A sends update on production"), "1")[0])

    def test_abstand_noetig_bei_gleicher_menge(self):
        # 561873 steht in drei Orders: Style allein ordnet nicht zu
        o, why = self.find(ev("Style 561873 ready"), "1")
        self.assertIsNone(o)

    def test_sammelbetreff_ohne_unterscheidung(self):
        e = ev("Vessel planning requested", _mail={"id": "m", "date": "2026-10-15 10:00", "subject": "Update / Sweat / Dawson / Kunde X"})
        self.assertIsNone(self.find(e, "1")[0])

    def test_positionsmenge_nur_mit_produktart(self):
        o2 = [order("A", "PO-A-ONE", [("111 Hoodie", 4000), ("112 Shirt", 10032)], 14032), order("B", "PO-A-TWO", [("113 Pant", 900)], 900)]
        idx = events.order_index(o2, [])
        res = content_match.match(ev("expecting 10,000 pcs ex-mill"), o2, idx)
        self.assertIsNone(res[0])   # 10000 ~ 10032 (Shirt), aber der Text nennt keine Produktart


class PlanSchwach(unittest.TestCase):
    def test_nur_notiz_kein_termin(self):
        e = ev("Dawson Fleece ready", details={"new_ex_factory": "2026-12-01"})
        with mock.patch.dict(os.environ, {"CONTENT_MATCH": "1"}):
            pl = events.plan([e], O, V, vendor_only=True, products=P)
        self.assertEqual(len(pl["orders"]), 1)
        p = pl["orders"][0]
        self.assertEqual(p["date_patch"], {})
        self.assertTrue(p["lines"][0]["weak"])
        self.assertIn("inhaltlich zugeordnet: Wort 'dawson'", p["lines"][0]["text"])
        self.assertEqual([w for _e, _o, w in pl["assigned"]], ["inhalt"])


class Backtest(unittest.TestCase):
    def test_kennungen_werden_ausgeblendet_styles_bleiben(self):
        t = order("O1", "PO-ALPHA-1", [("SNM26-004", 100)], 100, "Quelle PO ALP-55-25 Container HMMU6963097")
        t["poNumber"] = "ALP-55-25"
        idx = events.order_index([t], [])
        e = ev("Shipment HMMU6963097 of SNM26-004 under ALP-55-25", ref={"po_number": "ALP-55-25", "style": None, "container": "HMMU6963097"})
        m = content_backtest.mask(e, t, idx)
        self.assertNotIn("HMMU6963097", m["summary"]); self.assertNotIn("ALP-55-25", m["summary"]); self.assertIn("SNM26-004", m["summary"])
        self.assertIsNone(m["ref"]["po_number"])
        self.assertEqual(e["ref"]["po_number"], "ALP-55-25")   # Original unveraendert

    def test_wahrheit_nur_belegte_zeilen(self):
        o = {"id": "O1", "_notes": "[2026-10-01 10:00 ev:aaaaaaaa] SCHEDULE: x (Mail 1)\n[2026-10-02 10:00 ev:bbbbbbbb] SCHEDULE: y [Zuordnung: Stylecode im Ereignistext, nicht per PO-Nr belegt] (Mail 2)"}
        self.assertEqual(content_backtest.truth_map([o]), {"aaaaaaaa": "O1"})


if __name__ == "__main__":
    unittest.main()
