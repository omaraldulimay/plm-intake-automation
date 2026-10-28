import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import events, vendor_domains as vd, vendors_new as vn  # noqa: E402

V = [{"id": "VA", "name": "Lieferant A", "contacts": [{"email": "kontakt@lieferant-a.example"}]},
     {"id": "VT", "name": "Lieferant B Enterprises (Pvt) Ltd", "contacts": [{"email": "kontakt@lieferant-b.example"}]},
     {"id": "VB", "name": "Lieferant AD", "contacts": []}]
O = [{"id": "A1", "title": "PO-ALPHA-1", "manufacturer": {"id": "VA"}, "status": {"status": "In Production"}, "items": [{"name": "XW26-009 Tank"}]},
     {"id": "A2", "title": "PO-ALPHA-2", "manufacturer": {"id": "VA"}, "status": {"status": "In Production"}, "items": [{"name": "XW26-010 Tee"}]},
     {"id": "B1", "title": "PO-BRIDGE-1", "manufacturer": {"id": "VB"}, "status": {"status": "Approved"}, "items": [{"name": "Knitted Crewneck"}]}]


def ev(**kw):
    e = {"type": "SAMPLE", "vendor": "Lieferant A", "ref": {"po_number": None, "style": None, "container": None}, "summary": "Photo samples are ready", "details": {},
         "confidence": 0.9, "_mail": {"id": "m1", "date": "2026-10-15 10:00", "from": "Z <kontakt@lieferant-a.example>", "subject": "photo samples"}}
    e.update(kw)
    return e


def unmatched(e, orders=O):
    pl = events.plan([e], orders, V, vendor_only=True)
    return (pl["unmatched"][0]["reason"] if pl["unmatched"] else None), pl


class VendorPlausibel(unittest.TestCase):
    def test_code_ist_kein_lieferant(self):
        for s in ("561874_2510", "SNM26-005", "TE-26-2003-A", "AL29008", "26022"):
            self.assertFalse(events.vendor_plausible(s), s)
        for s in ("Lieferant A", "3M", "Lieferant AF", "LIEFERANT_AA", "Lieferant AD"):
            self.assertTrue(events.vendor_plausible(s), s)

    def test_vendor_of_ignoriert_code_und_nutzt_verlauf(self):
        e = ev(vendor="561874_2510", _vendor_inferred="VA")
        self.assertEqual(events.vendor_of(e, V)["id"], "VA")
        e2 = ev(vendor="561874_2510")
        self.assertIsNone(events.vendor_of(e2, [{"id": "X", "name": "561874_2510"}]))


class MusterInfo(unittest.TestCase):
    def test_mehrdeutiges_muster_wird_info(self):
        why, _ = unmatched(ev(ref={"po_number": None, "style": "XW26", "container": None}))
        self.assertTrue(why.startswith("info:"), why)

    def test_muster_ohne_lieferant_keine_order(self):
        why, _ = unmatched(ev(vendor=None, _mail={"id": "m", "date": "2026-10-15 10:00", "from": "kontakt@example.com", "subject": "x"}))
        self.assertTrue(why.startswith("info:"), why)

    def test_musterversand_mit_tracking_wird_info(self):
        e = ev(type="SHIPMENT", summary="Revised samples shipped via UPS.", details={"tracking": "1Z999", "qty": 3})
        self.assertTrue(unmatched(e)[0].startswith("info:"))

    def test_sperren(self):
        for kw in (dict(ref={"po_number": "PO26-036", "style": None, "container": None}),
                   dict(summary="Photo samples for 500 pcs ready"),
                   dict(summary="Sample invoice paid"),
                   dict(summary="Samples with price USD 9.70"),
                   dict(details={"qty": 5000}),
                   dict(details={"container": "TXGU4109596"}),
                   dict(summary="Proceed with bulk production after sample approval"),
                   dict(type="SHIPMENT", summary="Shipment of 39 cartons, goods shipped")):
            why, _ = unmatched(ev(**kw))
            self.assertFalse(str(why).startswith("info: Muster"), (kw, why))

    def test_eindeutige_order_bleibt_zugeordnet(self):
        why, pl = unmatched(ev(ref={"po_number": None, "style": "XW26-009", "container": None}))
        self.assertIsNone(why)
        self.assertEqual(pl["orders"][0]["id"], "A1")


class Domains(unittest.TestCase):
    def test_lernen_nur_stark_und_ab_zwei_mails(self):
        st = {}
        e1 = ev(_mail={"id": "m1", "from": "A <a@newvendor.com>"}); e2 = ev(_mail={"id": "m2", "from": "b@newvendor.com"})
        self.assertEqual(vd.learn(st, [(e1, "A1", "vendor_only")], O), [])
        vd.learn(st, [(e1, "A1", "ok")], O)
        self.assertEqual(vd.usable(st), {})
        self.assertEqual(vd.learn(st, [(e2, "A2", "alias")], O), [("newvendor.com", "VA", "aktiv")])
        self.assertEqual(vd.usable(st), {"newvendor.com": {"VA"}})

    def test_konflikt_frei_und_smilodox(self):
        st = {}
        a = ev(_mail={"id": "m1", "from": "a@d.com"}); b = ev(_mail={"id": "m2", "from": "a@d.com"})
        vd.learn(st, [(a, "A1", "ok"), (b, "B1", "ok")], O)
        self.assertEqual(vd.usable(st), {})
        for f in ("kontakt@example.com", "kontakt@firma.example", ""):
            self.assertEqual(vd.learn({}, [(ev(_mail={"id": "m", "from": f}), "A1", "ok")], O), [])

    def test_gelernte_domain_liefert_lieferant(self):
        orig = vd.load
        vd.load = lambda p: {"newvendor.com": {"vendor": "VA", "mails": ["m1", "m2"]}}
        try:
            dom = events.domain_vendors(V)
        finally:
            vd.load = orig
        e = ev(vendor=None, _mail={"id": "m9", "from": "q@newvendor.com"})
        self.assertEqual(events.vendor_of(e, V, None, dom)["id"], "VA")


class DomainAlias(unittest.TestCase):
    def spec(self, **kw):
        s = {"name": "Lieferant AC FZCO", "role": "SUPPLIER", "contacts": [{"email": "kontakt@lieferant-b.example"}]}
        s.update(kw); return s

    def test_alias_statt_neuanlage(self):
        self.assertEqual(vn.domain_alias(self.spec(), V)["id"], "VT")

    def test_nicht_bei_freemail_fremder_domain_spediteur_oder_namensaehnlich(self):
        self.assertIsNone(vn.domain_alias(self.spec(contacts=[{"email": "kontakt@example.com"}]), V))
        self.assertIsNone(vn.domain_alias(self.spec(contacts=[{"email": "a@other.com"}]), V))
        self.assertIsNone(vn.domain_alias(self.spec(role="FORWARDER"), V))
        self.assertIsNone(vn.domain_alias(self.spec(name="Lieferant A Exports"), V))

    def test_auto_setzt_alias_im_speicher(self):
        import tempfile, json
        d = tempfile.mkdtemp()
        with open(d + "/a_1.json", "w") as fh:
            json.dump({"doc_type": "PO", "vendor": "Lieferant AC FZCO", "items": [{"qty": 1}], "vendor_info": {"legal_name": "Lieferant AC FZCO", "role": "SUPPLIER",
                   "contacts": [{"email": "kontakt@lieferant-b.example"}]}}, fh)
        al = {}
        r = vn.auto(d, V, False, al)
        self.assertEqual(r[0]["status"], "ALIAS_AUTO")
        self.assertEqual(al, {"Lieferant AC FZCO": "Lieferant B Enterprises (Pvt) Ltd"})


class BridgeFall(unittest.TestCase):
    def test_stornierung_unbekannter_styles_ist_info(self):   # Info-Regel (28.10., Omar freigegeben): gestrichene Styles, die in KEINER Order stehen, ohne PO-/Rechnungsnummer = Info; Schalter INFO_REGEL=0 stellt den alten Klaerfall her
        e = {"type": "ORDER_CHANGE", "vendor": "Lieferant AD", "ref": {"po_number": None, "style": "ORA-T-526, 01955, FAB-001", "container": None},
             "summary": "Cancellation of multiple styles/items", "details": {"action": "cancel"}, "confidence": 0.9, "_mail": {"id": "m", "date": "2026-10-26 08:49", "from": "kontakt@firma.example", "subject": "LIEFERANT_AD Comments"}}
        why, _ = unmatched(e)
        self.assertTrue(why.startswith("info: Regel Muster/Streichung"), why)
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"INFO_REGEL": "0"}):
            why, _ = unmatched(e)
        self.assertEqual(why, "keine Order gefunden")


if __name__ == "__main__":
    unittest.main()
