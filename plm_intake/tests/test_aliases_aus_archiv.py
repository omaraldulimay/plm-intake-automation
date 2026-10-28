import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import aliases_aus_archiv as aa, events  # noqa: E402

V = [{"id": "VW", "name": "Lieferant T"}, {"id": "VH", "name": "Lieferant U"}, {"id": "VK", "name": "Lieferant W"}, {"id": "VA", "name": "Lieferant A"}]


def order(i, title, vid, po=None, status="In Transit"):
    return {"id": i, "title": title, "orderNumber": 1, "manufacturer": {"id": vid}, "status": {"status": status}, "poNumber": po, "items": []}


O = [order("W1", "PO-LIEFERANT_T-PO26005SG-W", "VW", po="PO26005SG-W"), order("H1", "PO-LIEFERANT_U-HI2603100157", "VH", po="HI2603100157", status="Complete"),
     order("K1", "PO-LIEFERANT_W-26071-DE-EA-2", "VK", po="26071-DE-EA-2"), order("K2", "PO-LIEFERANT_W-26071-DE-EA-2EXTRA", "VK", po="26071-DE-EA-2EXTRA"),
     order("A1", "PO-ALPHA-KUNDE_X-DE-2026-05-08", "VA"), order("A2", "PO-ALPHA-KUNDE_X-CH-2026-05-11", "VA")]
O[2]["items"] = [{"name": "A", "product": {"id": "p1"}}, {"name": "B", "product": {"id": "p2"}}, {"name": "C", "product": {"id": "p3"}}]
O[3]["items"] = [{"name": "A", "product": {"id": "p1"}}]
O[4]["items"] = [{"name": "A", "product": {"id": "p4"}}]
O[5]["items"] = [{"name": "A", "product": {"id": "p4"}}]
PRODUCTS = [{"id": "p1", "sku": "HY29582"}, {"id": "p2", "sku": "HY29583"}, {"id": "p3", "sku": "HY29587"}, {"id": "p4", "sku": "561876"}]
CTX = {"orders": O, "vendors": V, "products": PRODUCTS, "aliases": {}, "dom": {}}


def mail(mid, thread, subject, att=(), text="", frm="x@y.com"):
    return {"id": mid, "thread": thread, "date": "2026-10-01 10:00", "from": frm, "subject": subject, "att": list(att), "att_raw": list(att), "text": text}


def ev(mid, subject, vendor, **details):
    return {"type": "SHIPMENT", "vendor": vendor, "ref": {"po_number": None, "style": None, "container": details.pop("container", None)}, "summary": "x", "details": details, "key": mid,
            "_mail": {"id": mid, "date": "2026-10-02 10:00", "from": "a@b.com", "subject": subject, "thread": None}}


class Archiv(unittest.TestCase):
    def test_parse_block_und_anhangsprefix(self):
        b = ("\nMessage-ID: abc123\nThread-ID: t1\nDatum: 2026-10-12 10:00\nVon: X <x@y.com>\nAn: z\nBetreff: Re: IM.001370.26 // H.W.\n"
             "Anhaenge: 2026-10-12_1a131b4f34293d84_PO26005SG-W-2 packing list.pdf | 2026-10-12_1a131b4f34293d84_BL.pdf\n----- TEXT -----\nHallo\n")
        m = aa.parse_block(b)
        self.assertEqual((m["id"], m["thread"], m["subject"]), ("abc123", "t1", "Re: IM.001370.26 // H.W."))
        self.assertEqual(m["att"], ["PO26005SG-W-2 packing list.pdf", "BL.pdf"]); self.assertTrue(m["att_raw"][0].startswith("2026-10-12_"))
        self.assertIsNone(aa.parse_block("kein Header"))

    def test_spedition_akte_ueber_verlauf_mit_anhangsnamen(self):   # IM.001370 -> Lieferant T: im Verlauf liegt 'PO26005SG-W-2 packing list and invoice'
        mails = [mail("m1", "T1", "IM.001370.26 // H.W. // Ningbo"), mail("m2", "T1", "AW: IM.001370.26", att=["PO26005SG-W-2 packing list and invoice V2(1).pdf"])]
        e = ev("e1", "AW: AW: IM.001370.26 // H.W. // Ningbo", "SPEDITION_B Spedition")
        prop, drop = aa.derive(CTX, mails, [e])
        self.assertEqual([(p["key"], p["order_id"]) for p in prop], [("IM.001370.26", "W1")]); self.assertEqual(drop, [])
        self.assertEqual(len(prop[0]["events"]), 1)

    def test_kennung_in_zwei_verlaeufen_mit_zwei_orders_kein_alias(self):
        mails = [mail("m1", "T1", "IM.001370.26 PO26005SG-W"), mail("m2", "T2", "IM.001370.26 HI2603100157")]
        prop, drop = aa.derive(CTX, mails, [ev("e1", "IM.001370.26", None)])
        self.assertEqual(prop, []); self.assertEqual(len(drop), 1); self.assertIn("mehrere Orders", drop[0]["grund"])

    def test_lieferant_passt_nicht(self):
        mails = [mail("m1", "T1", "IM.001370.26 PO26005SG-W")]
        prop, drop = aa.derive(CTX, mails, [ev("e1", "IM.001370.26", "Lieferant U")])
        self.assertEqual(prop, []); self.assertIn("passt nicht", drop[0]["grund"])

    def test_lieferantenname_bei_ein_order_lieferant(self):   # 'Lieferant U' im Betreff, Lieferant U hat genau eine Order
        mails = [mail("m1", "T9", "Fwd: IM.001003.26 // H.W. // Lieferant U / SEGU1348900"), mail("m2", "T9", "AW: Warnstreik IM.001003.26")]
        prop, _ = aa.derive(CTX, mails, [ev("e1", "AW: Warnstreik IM.001003.26 // SEGU1348900", "Lieferant U")])
        self.assertEqual({p["order_id"] for p in prop}, {"H1"}); self.assertEqual({p["key"] for p in prop}, {"IM.001003.26", "SEGU1348900"})

    def test_laengere_kennung_geht_vor(self):   # ...-2 steckt in ...-2EXTRA: nur die spezifischere Order
        ids = aa.order_ids(O)
        self.assertEqual(aa.orders_in("PI OF 26071-DE-EA-2EXTRA.xlsx", ids), {"K2"})
        self.assertEqual(aa.orders_in("PI OF 26071-DE-EA-2.xlsx", ids), {"K1"})
        self.assertEqual(aa.orders_in("PI OF 26071-DE-EA-2 - copy.xlsx | PI OF 26071-DE-EA-2EXTRA.xlsx", ids), {"K1", "K2"})   # zwei Dateien = zwei Orders

    def test_xlsx_rechnung_styles_nur_eine_order(self):
        rows = [("S", ["INV NO.", "NX226083"]), ("S", ["HY29582", "BLACK"]), ("S", ["HY29583", "NAVY"]), ("S", ["HY29587"])]
        inv, cand = aa.xlsx_invoice_evidence(rows, aa.sku_index(O, PRODUCTS))
        self.assertEqual((inv, cand), ({"NX226083"}, {"K1"}))
        skus2 = dict(aa.sku_index(O, PRODUCTS)); skus2["K2"] = {"hy29582", "hy29583", "hy29587"}   # zweite Order mit allen Styles: mehrere Treffer (nur Gegenprobe)
        self.assertEqual(aa.xlsx_invoice_evidence(rows, skus2)[1], {"K1", "K2"})
        inv, cand = aa.xlsx_invoice_evidence([("S", ["INV NO.", "NX1234567"]), ("S", ["HY29582"])], aa.sku_index(O, PRODUCTS))   # nur ein Style: zu wenig
        self.assertEqual(cand, set())

    def test_xlsx_im_anhang_wird_alias(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl fehlt")
        d = tempfile.mkdtemp()
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["INV NO.", "NX226083"]); ws.append(["HY29582", "BLACK", 100]); ws.append(["HY29583", "NAVY", 50]); ws.append(["HY29587", "NAVY", 20])
        wb.save(os.path.join(d, "2026-10-14_1a13a6420646f088_IN&PACKING LIST-26071.xlsx"))
        m = mail("e1", "T5", "Re: ISPOB3.429-5LIEFERANTW", att=["IN&PACKING LIST-26071.xlsx"])   # die Mail des Ereignisses (e1) liegt im Archiv; der Anhang im Verlauf
        m["att_raw"] = ["2026-10-14_1a13a6420646f088_IN&PACKING LIST-26071.xlsx"]
        m["text"] = "Invoice NX226083 attached"
        e = ev("e1", "Re: ISPOB3.429-5LIEFERANTW", "Lieferant W", invoice_no="NX226083")
        prop, _ = aa.derive(CTX, [m], [e], att_dir=d)
        self.assertEqual([(p["key"], p["order_id"]) for p in prop], [("NX226083", "K1")])

    def test_widerspruch_verlauf_gegen_rechnungsstyles_kein_alias(self):   # Fall NX226083: Verlauf nennt ...-2EXTRA, die Styles der Rechnung passen zu ...-2 UND einer weiteren Order
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl fehlt")
        d = tempfile.mkdtemp()
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["INV NO.", "NX226083"]); ws.append(["HY29582"]); ws.append(["HY29583"]); ws.append(["HY29587"])
        wb.save(os.path.join(d, "x.xlsx"))
        m = mail("e1", "T5", "Re: PI OF 26071-DE-EA-2EXTRA", att=["x.xlsx"]); m["att_raw"] = ["x.xlsx"]
        ctx = dict(CTX, orders=O + [order("K3", "PO-LIEFERANT_W-2026-04-29", "VK")])
        ctx["orders"][-1]["items"] = list(O[2]["items"])
        prop, drop = aa.derive(ctx, [m], [ev("e1", "Re: PI OF 26071-DE-EA-2EXTRA", "Lieferant W", invoice_no="NX226083")], att_dir=d)
        self.assertEqual(prop, []); self.assertIn("widerspricht", drop[0]["grund"])

    def test_containerliste_ein_land_eine_order(self):
        rows = [("Containerübersicht", ["Container #", "Container No", "Ship Date", "Supplier", "Article No.", "Design Variant", "Color", "Country", "Shipped Qty", "Packing List / Ref."]),
                ("Containerübersicht", ["1", "FFAU-618847-5", "x", "Lieferant A Pvt Ltd", "561876.0", "Hoodie", "Black", "DE", "100", "AK/568/26"]),
                ("Containerübersicht", ["7", "EGHU-914348-0", "x", "Lieferant A Pvt Ltd", "561876.0", "Hoodie", "Black", "DE", "100", "AK/588/26"]),
                ("Containerübersicht", ["7", "EGHU-914348-0", "x", "Lieferant A Pvt Ltd", "561876.0", "Hoodie", "Black", "CH", "100", "AK/588/26"]),
                ("Containerübersicht", ["8", "GAOU-642138-0", "x", "Lieferant A Pvt Ltd", "561876.0", "Hoodie", "Black", "OSDE", "100", "AK/589/26"])]
        out = aa.container_list(rows, O, V, aa.sku_index(O, PRODUCTS))
        self.assertEqual(out, {"ffau6188475": "A1", "ak56826": "A1"})   # EGHU: zwei Laender, GAOU: Land unbekannt -> kein Alias


class SubjectAlias(unittest.TestCase):
    def test_akte_im_betreff_trifft_nur_ueber_alias(self):
        e = ev("e2", "Fwd: AW: Warnstreik IM.001003.26 // H.W. // Lieferant U", "Lieferant U")
        e["type"] = "DELAY"
        ok, _ = events.find_order(e, O, V, {}, {}, vendor_only=True)
        self.assertIsNone(ok)
        o, why = events.find_order(e, O, V, {"IM.001003.26": "PO-LIEFERANT_U-HI2603100157"}, {}, vendor_only=True)
        self.assertEqual((o["id"], why), ("H1", "alias"))

    def test_invoice_no_zaehlt_als_schluessel(self):
        e = ev("e3", "Rechnung", "Lieferant W", invoice_no="NX226083")
        o, why = events.find_order(e, O, V, {"NX226083": "PO-LIEFERANT_W-26071-DE-EA-2"}, {}, vendor_only=True)
        self.assertEqual((o["id"], why), ("K1", "alias"))


if __name__ == "__main__":
    unittest.main()
