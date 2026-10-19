import copy
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import events  # noqa: E402

VENDORS = [{"id": "V_XW", "name": "Lieferant C"}, {"id": "V_CM", "name": "Ningbo Lieferant D Co., Ltd"}]
ORDERS = [{"id": "O28", "orderNumber": 28, "title": "PO-XW-SM260513", "poNumber": "", "manufacturer": {"id": "V_XW"}, "items": [{"name": "XW-041 Men Windbreaker"}]},
          {"id": "O33", "orderNumber": 33, "title": "PO-XW-SM260730", "manufacturer": {"id": "V_XW"}, "items": [{"name": "XW-042 Rain Jacket"}]},
          {"id": "O25", "orderNumber": 25, "title": "PO-LIEFERANT_D-ALI20260821", "manufacturer": {"id": "V_CM"}, "items": [{"name": "AN-43 Flared Leggings"}]}]


def ev(**kw):
    e = {"type": "SCHEDULE", "vendor": "Lieferant C", "ref": {"po_number": "XW-SM260513", "style": None, "container": None}, "date": "2026-10-15",
         "summary": "ETD verschoben", "details": {"new_etd": "2026-10-15"}, "confidence": 0.9, "key": "k1",
         "_mail": {"id": "m1", "date": "2026-10-12 18:00", "from": "x", "subject": "s"}}
    e.update(kw)
    return e


class LieferantenZuordnung(unittest.TestCase):
    V = [{"id": "VA", "name": "Lieferant A"}, {"id": "VB", "name": "Lieferant C"}, {"id": "VC", "name": "Lieferant D"}]
    O = [{"id": "A1", "title": "PO-ALPHA-1", "manufacturer": {"id": "VA"}, "status": {"status": "In Production"}, "items": []},
         {"id": "B1", "title": "PO-XW-1", "manufacturer": {"id": "VB"}, "status": {"status": "In Production"}, "items": []},
         {"id": "B2", "title": "PO-XW-0", "manufacturer": {"id": "VB"}, "status": {"status": "Complete"}, "items": []},
         {"id": "C1", "title": "PO-LIEFERANT_D-1", "manufacturer": {"id": "VC"}, "status": {"status": "Draft"}, "items": []},
         {"id": "C2", "title": "PO-LIEFERANT_D-2", "manufacturer": {"id": "VC"}, "status": {"status": "Approved"}, "items": []}]

    def e(self, **kw):
        base = {"type": "SHIPMENT", "vendor": "Lieferant A", "ref": {"po_number": None, "style": None, "container": None}, "date": None, "summary": "Verladung", "details": {}, "confidence": 0.9,
                "_mail": {"id": "m", "date": "2026-10-15 10:00"}}
        base.update(kw); return base

    def test_standard_bleibt_streng(self):   # ohne vendor_only wie bisher: Lieferant allein reicht nicht
        self.assertIsNone(events.find_order(self.e(), self.O, self.V)[0])

    def test_einzige_laufende_order_wird_schwach_zugeordnet(self):
        o, why = events.find_order(self.e(), self.O, self.V, vendor_only=True); self.assertEqual((o["id"], why), ("A1", "vendor_only"))

    def test_abgeschlossene_orders_zaehlen_nicht_mit(self):
        o, why = events.find_order(self.e(vendor="Lieferant C"), self.O, self.V, vendor_only=True); self.assertEqual(o["id"], "B1")

    def test_mehrere_laufende_orders_sind_mehrdeutig(self):
        o, why = events.find_order(self.e(vendor="Lieferant D"), self.O, self.V, vendor_only=True); self.assertIsNone(o); self.assertIn("mehrdeutig", why)

    def test_muster_ohne_po_ist_info_kein_handlungsbedarf(self):
        o, why = events.find_order(self.e(type="SAMPLE"), self.O, self.V, vendor_only=True); self.assertIsNone(o); self.assertTrue(why.startswith("info:"))

    def test_lieferanten_alias_loest_namensvariante(self):
        e = self.e(vendor="Lieferant C")
        self.assertIsNone(events.find_order(e, self.O, self.V, vendor_only=True)[0])
        self.assertEqual(events.find_order(e, self.O, self.V, vendor_aliases={"Lieferant C": "Lieferant C"}, vendor_only=True)[0]["id"], "B1")

    def test_schwache_zuordnung_aendert_nie_termine_oder_zahlungen(self):
        e = self.e(type="SCHEDULE", details={"new_etd": "2026-11-01"})
        p = events.plan([e], self.O, self.V, vendor_only=True)["orders"][0]
        self.assertEqual(p["date_patch"], {}); self.assertEqual(p["pay"], []); self.assertIn("nicht per PO-Nr belegt", p["lines"][0]["text"])
        pay = self.e(type="PAYMENT", details={"paid": True, "amount": 100})
        self.assertEqual(events.plan([pay], self.O, self.V, vendor_only=True)["orders"][0]["pay"], [])

    def test_starke_zuordnung_aendert_weiter_termine(self):
        e = self.e(type="SCHEDULE", ref={"po_number": "ALPHA-1", "style": None, "container": None}, details={"new_etd": "2026-11-01"})
        self.assertTrue(events.plan([e], self.O, self.V, vendor_only=True)["orders"][0]["date_patch"])


class StatusProzess(unittest.TestCase):
    ST = {n: {"id": "S" + str(i), "status": n, "color": "#000", "order": i} for n, i in events.STATUS_ORDER.items()}

    def orders(self, cur="Draft"):
        return [{"id": "O1", "title": "PO-XYZ-100", "poNumber": "XYZ-100", "manufacturer": {"id": "V1"}, "status": dict(self.ST[cur]), "items": []},
                {"id": "O2", "title": "PO-XYZ-200", "manufacturer": {"id": "V1"}, "status": dict(self.ST["Complete"]), "items": []},
                {"id": "O3", "title": "PO-ALLE", "manufacturer": {"id": "V9"}, "status": {k: v for k, v in self.ST["In Transit"].items()}, "items": []},
                {"id": "O4", "title": "PO-DRAFT", "manufacturer": {"id": "V9"}, "status": dict(self.ST["Draft"]), "items": []},
                {"id": "O5", "title": "PO-APP", "manufacturer": {"id": "V9"}, "status": dict(self.ST["Approved"]), "items": []},
                {"id": "O6", "title": "PO-INP", "manufacturer": {"id": "V9"}, "status": dict(self.ST["In Production"]), "items": []},
                {"id": "O7", "title": "PO-QC", "manufacturer": {"id": "V9"}, "status": dict(self.ST["QC"]), "items": []}]

    def ev(self, ms, po="XYZ-100", conf=0.9, typ="SHIPMENT"):
        return {"type": typ, "vendor": "V", "ref": {"po_number": po, "style": None, "container": None}, "summary": "s " + str(ms), "details": {"milestone": ms}, "confidence": conf,
                "_mail": {"id": "m", "date": "2026-10-15 10:00"}}

    def tgt(self, ev, cur="Draft", po_cur=None):
        pl = events.plan([ev], self.orders(cur), [{"id": "V1", "name": "V"}])
        return pl["orders"][0].get("status", {}).get("to", {}).get("status") if pl["orders"] else None

    def test_meilensteine_fuehren_zur_naechsten_stufe(self):
        for ms, want in (("PI_CONFIRMED", "Approved"), ("DEPOSIT_PAID", "Approved"), ("PRODUCTION_STARTED", "In Production"), ("INSPECTION_PASSED", "QC"), ("SHIPPED", "In Transit")):
            self.assertEqual(self.tgt(self.ev(ms)), want, ms)

    def test_nie_rueckwaerts_und_nie_gleich(self):
        self.assertIsNone(self.tgt(self.ev("PI_CONFIRMED"), cur="In Production"))
        self.assertIsNone(self.tgt(self.ev("SHIPPED"), cur="In Transit"))

    def test_complete_wird_nie_automatisch_gesetzt_und_nie_verlassen(self):
        self.assertIsNone(self.tgt(self.ev("DELIVERED")))
        self.assertIsNone(self.tgt(self.ev("SHIPPED", po="XYZ-200")))   # O2 ist Complete

    def test_unbekannter_meilenstein_zu_niedrige_konfidenz_und_muster_zaehlen_nicht(self):
        self.assertIsNone(self.tgt(self.ev("IRGENDWAS")))
        self.assertIsNone(self.tgt(self.ev("SHIPPED", conf=0.6)))
        self.assertIsNone(self.tgt(self.ev("SHIPPED", typ="SAMPLE")))

    def test_mehrere_meilensteine_hoechste_stufe_gewinnt(self):
        pl = events.plan([self.ev("PI_CONFIRMED"), self.ev("PRODUCTION_STARTED"), self.ev("DEPOSIT_PAID")], self.orders(), [{"id": "V1", "name": "V"}])
        self.assertEqual(pl["orders"][0]["status"]["to"]["status"], "In Production")

    def test_schwache_zuordnung_aendert_nie_den_status(self):
        e = self.ev("SHIPPED", po=None); e["vendor"] = "V"
        pl = events.plan([e], self.orders(), [{"id": "V1", "name": "V"}], vendor_only=True)
        self.assertTrue(pl["orders"] == [] or "status" not in pl["orders"][0])


class AliasZuordnung(unittest.TestCase):
    O = [{"id": "A", "title": "PO-LIEFERANT_W-2026-04-29", "manufacturer": {"id": "V"}, "items": []}, {"id": "B", "title": "PO-ANDERS", "manufacturer": {"id": "V"}, "items": []}]
    V = [{"id": "V", "name": "Kyle"}]

    def e(self, po):
        return {"type": "PAYMENT", "vendor": "Kyle", "ref": {"po_number": po, "style": None, "container": None}, "summary": "x", "details": {}, "confidence": 0.9, "_mail": {"id": "m", "date": "2026-10-15 10:00"}}

    def test_alias_trifft_auch_mit_suffix(self):
        al = {"ISPOB3.429": "PO-LIEFERANT_W-2026-04-29"}
        self.assertEqual(events.find_order(self.e("ISPOB3.429-5"), self.O, self.V, al)[0]["id"], "A")
        self.assertEqual(events.find_order(self.e("ISPOB3.429"), self.O, self.V, al)[0]["id"], "A")

    def test_kurze_alias_matchen_nie_per_praefix(self):
        self.assertIsNone(events.find_order(self.e("AB12-9999"), self.O, self.V, {"AB12": "PO-LIEFERANT_W-2026-04-29"})[0])


class Zeilenbeschriftung(unittest.TestCase):
    def test_belege_heissen_beleg_und_ereignisse_behalten_ihren_typ(self):
        base = {"type": "PAYMENT", "summary": "INVOICE 1 | 5 Stk", "details": {"doc_type": "INVOICE", "paid": False}, "_mail": {"id": "m", "date": "2026-10-15 10:00"}}
        self.assertIn("] BELEG INVOICE: ", events.line(base))
        self.assertIn("] SHIPMENT: ", events.line(dict(base, type="SHIPMENT", details={"milestone": "SHIPPED"})))


class Zuordnung(unittest.TestCase):
    def test_po_nummer_im_titel(self):
        o, _ = events.find_order(ev(), ORDERS, VENDORS); self.assertEqual(o["id"], "O28")

    def test_style_als_fallback(self):
        o, _ = events.find_order(ev(ref={"po_number": None, "style": "AN-43"}, vendor="LIEFERANT_D"), ORDERS, VENDORS); self.assertEqual(o["id"], "O25")

    def test_nur_lieferant_reicht_nicht(self):
        o, why = events.find_order(ev(ref={"po_number": None, "style": None}), ORDERS, VENDORS); self.assertIsNone(o); self.assertIn("keine Order", why)

    def test_mehrdeutig_wird_nicht_geraten(self):
        orders = ORDERS + [{"id": "O99", "orderNumber": 99, "title": "PO-XW-SM260513-NACHTRAG", "manufacturer": {"id": "V_CM"}, "items": []}]
        o, why = events.find_order(ev(vendor=None), orders, VENDORS); self.assertIsNone(o); self.assertIn("mehrdeutig", why)

    def test_lieferant_als_tiebreaker(self):
        orders = ORDERS + [{"id": "O99", "orderNumber": 99, "title": "PO-XW-SM260513-NACHTRAG", "manufacturer": {"id": "V_CM"}, "items": []}]
        o, _ = events.find_order(ev(), orders, VENDORS); self.assertEqual(o["id"], "O28")

    def test_alias_tabelle_fuer_lieferantennummern(self):
        e = ev(ref={"po_number": "ISPOB3.429", "style": None}, vendor="Lieferant W")
        orders = ORDERS + [{"id": "OK", "orderNumber": 20, "title": "PO-LIEFERANT_W-2026-04-29", "manufacturer": {"id": "V_K"}, "items": []}]
        self.assertIsNone(events.find_order(e, orders, VENDORS)[0])
        self.assertEqual(events.find_order(e, orders, VENDORS, {"ISPOB3.429": "PO-LIEFERANT_W-2026-04-29"})[0]["id"], "OK")
        self.assertIsNone(events.find_order(e, orders, VENDORS, {"ISPOB3.429": "GIBTS-NICHT"})[0])

    def test_zu_kurze_nummer_wird_ignoriert(self):
        o, _ = events.find_order(ev(ref={"po_number": "XW", "style": None}), ORDERS, VENDORS); self.assertIsNone(o)


class ZuordnungDurchKennungStyleVerlauf(unittest.TestCase):
    V = [{"id": "VA", "name": "Lieferant A"}, {"id": "VX", "name": "Lieferant C"}]
    PRODUCTS = [{"id": "P1", "sku": "AL29008"}, {"id": "P2", "sku": "AL29012"}]
    O = [{"id": "A1", "title": "PO-ALPHA-1", "manufacturer": {"id": "VA"}, "status": {"status": "In Production"}, "items": [{"name": "Hoodie", "product": {"id": "P1"}}], "_notes": ""},
         {"id": "A2", "title": "PO-ALPHA-KUNDE_X-POLY", "manufacturer": {"id": "VA"}, "status": {"status": "In Production"}, "items": [{"name": "Pant", "product": {"id": "P2"}}], "_notes": ""},
         {"id": "X1", "title": "PO-XW-1", "manufacturer": {"id": "VX"}, "status": {"status": "In Transit"}, "items": [],
          "_notes": "[2026-10-12 18:00 ev:aaaa1111] SHIPMENT: Sendung HBL XIME26070257 / MBL XIA1965473 (Mail 1a131b5dbbcc7e59)"},
         {"id": "X2", "title": "PO-XW-2", "manufacturer": {"id": "VX"}, "status": {"status": "In Production"}, "items": [], "_notes": ""}]

    def e(self, **kw):
        base = {"type": "SHIPMENT", "vendor": None, "ref": {"po_number": None, "style": None, "container": None}, "date": None, "summary": "x", "details": {}, "confidence": 0.9, "key": "k",
                "_mail": {"id": "m", "date": "2026-10-15 10:00", "subject": "Shipment update 4x40HQ Xiamen Hamburg"}}
        base.update(kw); return base

    def find(self, e, **kw):
        idx = events.order_index(self.O, self.PRODUCTS)
        return events.find_order(e, self.O, self.V, vendor_only=True, idx=idx, **kw)

    def test_style_trifft_ueber_produkt_sku(self):
        o, why = self.find(self.e(type="QUALITY", vendor="Lieferant A", ref={"po_number": None, "style": "AL29008", "container": None}))
        self.assertEqual((o["id"], why), ("A1", "ok"))

    def test_bekannte_kennung_aus_notizen_trifft_die_order(self):
        o, why = self.find(self.e(summary="Mitteilung des HS-Codes fuer HBL NO. XIME26070257 / MBL NO. XIA1965473"))
        self.assertEqual((o["id"], why), ("X1", "ok"))

    def test_mail_ids_und_marker_zaehlen_nicht_als_kennung(self):
        self.assertEqual(events.id_tokens("ev:aaaa1111 Mail 1a131b5dbbcc7e59 2026-10-12 22:01"), set())
        self.assertIn("xime26070257", events.id_tokens("HBL XIME26070257"))

    def test_unbekannte_kennung_bleibt_ohne_order(self):
        o, why = self.find(self.e(summary="HBL ZZZZ99999999 erhalten"))
        self.assertIsNone(o)

    def test_info_auch_bei_style_wenn_muster_ohne_order(self):
        o, why = self.find(self.e(type="SAMPLE", vendor="Lieferant A", ref={"po_number": None, "style": "55077", "container": None}))
        self.assertIsNone(o); self.assertTrue(why.startswith("info:"))

    def test_projektname_im_text_waehlt_unter_mehreren_laufenden_orders(self):
        o, why = self.find(self.e(vendor="Lieferant A", summary="Confirmed EXW dates for KUNDE_X Polystyles: 50% on 20 Oct"))
        self.assertEqual((o["id"], why), ("A2", "vendor_title"))
        o, why = self.find(self.e(vendor="Lieferant A", summary="Confirmed EXW dates"))
        self.assertIsNone(o); self.assertIn("mehrdeutig", why)

    def test_paketdienst_ohne_bestellbezug_ist_info_mit_kennung_aber_zuordnung(self):
        o, why = self.find(self.e(type="PAYMENT", vendor="UPS", summary="Importgebuehren fuer UPS-Sendung bezahlt"))
        self.assertIsNone(o); self.assertTrue(why.startswith("info:"))
        o, why = self.find(self.e(type="SHIPMENT", vendor="Spedition B", summary="HBL XIME26070257 Verzoegerung durch Streik"))
        self.assertEqual(o["id"], "X1")   # bekannte Kennung gewinnt vor der Dienstleister-Regel

    def test_laufende_order_gewinnt_gegen_abgeschlossene(self):
        orders = [dict(self.O[2], status={"status": "Complete"}, _notes="HBL XIME26070257"), dict(self.O[3], _notes="HBL XIME26070257")]
        idx = events.order_index(orders, self.PRODUCTS)
        o, why = events.find_order(self.e(summary="HBL XIME26070257"), orders, self.V, vendor_only=True, idx=idx)
        self.assertEqual(o["id"], "X2")

    def test_verlauf_vererbt_order_nur_als_notiz(self):
        a = self.e(key="k1", ref={"po_number": "PO-XW-1", "style": None, "container": None}, type="SCHEDULE", details={"new_etd": "2026-11-01"}, summary="ETD neu")
        b = self.e(key="k2", summary="Spediteur weist auf Streik hin", type="DELAY")
        c = self.e(key="k3", summary="ETA verschoben", type="SCHEDULE", details={"new_etd": "2026-12-24"}, confidence=0.95)
        pl = events.plan([a, b, c], self.O, self.V, vendor_only=True, products=self.PRODUCTS)
        self.assertEqual(len(pl["orders"]), 1); p = pl["orders"][0]
        self.assertEqual(p["id"], "X1"); self.assertEqual(len(p["lines"]), 3)
        weak = [l for l in p["lines"] if l["weak"]]; self.assertEqual(len(weak), 2)
        self.assertEqual(p["date_patch"].get("etdEstimatedDate", "")[:10], "2026-11-01")   # Termin nur vom belegten Ereignis, nie vom geerbten

    def test_verlauf_loest_keine_mehrdeutigkeit_zwischen_anderen_orders_auf(self):
        a = self.e(key="k1", ref={"po_number": "PO-XW-1", "style": None, "container": None}, summary="ETD neu")
        b = self.e(key="k2", vendor="Lieferant A", ref={"po_number": "PO-ALPHA", "style": None, "container": None}, summary="x")   # trifft A1 und A2 per Titel (mehrdeutig)
        pl = events.plan([a, b], self.O, self.V, vendor_only=True, products=self.PRODUCTS)
        self.assertEqual([u["event"]["key"] for u in pl["unmatched"]], ["k2"])

    def test_zu_kurzer_oder_allgemeiner_betreff_verbindet_nichts(self):
        self.assertIsNone(events.thread_key(self.e(_mail={"subject": "Re: Update"})))
        self.assertEqual(events.thread_key(self.e(_mail={"subject": "RE: Fwd: Shipment update 4x40HQ"})), events.thread_key(self.e(_mail={"subject": "Shipment update 4x40HQ"})))


class Plan(unittest.TestCase):
    def test_zeile_hat_marker_datum_und_mail(self):
        p = events.plan([ev()], ORDERS, VENDORS)["orders"][0]
        l = p["lines"][0]["text"]
        self.assertRegex(l, r"^\[2026-10-12 18:00 ev:[0-9a-f]{8}\] SCHEDULE: ETD verschoben \(Mail m1\)$")

    def test_datum_nur_bei_hoher_konfidenz_und_konkretem_datum(self):
        self.assertEqual(events.plan([ev()], ORDERS, VENDORS)["orders"][0]["date_patch"], {"etdEstimatedDate": "2026-10-15T00:00:00.000Z"})
        self.assertEqual(events.plan([ev(confidence=0.5)], ORDERS, VENDORS)["orders"][0]["date_patch"], {})
        self.assertEqual(events.plan([ev(details={})], ORDERS, VENDORS)["orders"][0]["date_patch"], {})
        self.assertEqual(events.plan([ev(type="DELAY")], ORDERS, VENDORS)["orders"][0]["date_patch"], {})
        self.assertEqual(events.plan([ev(details={"new_etd": "bald"})], ORDERS, VENDORS)["orders"][0]["date_patch"], {})

    def test_spaeteres_ereignis_gewinnt(self):
        a = ev(key="a", details={"new_etd": "2026-10-15"}); b = ev(key="b", details={"new_etd": "2026-10-30"}, _mail={"id": "m2", "date": "2026-10-13 09:00"})
        self.assertEqual(events.plan([b, a], ORDERS, VENDORS)["orders"][0]["date_patch"]["etdEstimatedDate"], "2026-10-30T00:00:00.000Z")

    def test_zahlung_nur_wenn_paid_true(self):
        mk = lambda paid: ev(type="PAYMENT", key="p", details={"paid": paid, "amount": 52464})
        self.assertEqual(events.plan([mk(True)], ORDERS, VENDORS)["orders"][0]["pay"][0]["amount"], 52464.0)
        self.assertEqual(events.plan([mk(False)], ORDERS, VENDORS)["orders"][0]["pay"], [])
        self.assertEqual(events.plan([mk("ja")], ORDERS, VENDORS)["orders"][0]["pay"], [])

    def test_order_aenderungen_nur_notiz_nie_automatisch(self):
        p = events.plan([ev(type="ORDER_CHANGE", details={"qty": 999, "new_etd": "2026-10-15"})], ORDERS, VENDORS)["orders"][0]
        self.assertEqual(p["date_patch"], {}); self.assertEqual(p["pay"], []); self.assertEqual(len(p["lines"]), 1)

    def test_nicht_zugeordnet_im_bericht(self):
        pl = events.plan([ev(ref={"po_number": "GIBTSNICHT1", "style": None}, vendor="Unbekannt")], ORDERS, VENDORS)
        self.assertEqual(pl["orders"], []); self.assertEqual(len(pl["unmatched"]), 1); self.assertIn("Nicht zugeordnet", events.report(pl))

    def test_gleiches_ereignis_doppelt_nur_einmal(self):
        self.assertEqual(len(events.plan([ev(), ev()], ORDERS, VENDORS)["orders"][0]["lines"]), 1)

    def test_bankdaten_werden_auch_hier_entfernt(self):
        l = events.plan([ev(summary="Zahlung an IBAN DE89 3704 0044 0532 0130 00 erfolgt")], ORDERS, VENDORS)["orders"][0]["lines"][0]["text"]
        self.assertNotIn("DE89", l); self.assertIn("Bankdaten entfernt", l)

    def test_lange_texte_werden_gekuerzt(self):
        l = events.plan([ev(summary="x" * 5000)], ORDERS, VENDORS)["orders"][0]["lines"][0]["text"]; self.assertLess(len(l), 520)


@unittest.skipUnless(shutil.which("node"), "node fehlt")
class Skript(unittest.TestCase):
    BASE = {"id": "O28", "title": "PO-T", "totalCost": 100, "totalNumberOfPieces": 10, "manufacturer": {"id": "V"}, "notes": "Quelle: PI.", "etdEstimatedDate": 1790000000000,
            "exFactoryExpectedDate": 1780000000000,
            "items": [{"name": "A", "product": {"id": "P"}, "variants": [{"name": "Black", "variantId": "VV", "amounts": [{"key": "S", "quantity": 10, "price": 10, "cost": 100}]}]}],
            "payments": [{"name": "30%", "status": "Unpaid", "amount": 30, "dueDate": 1}, {"name": "70%", "status": "Unpaid", "amount": 70, "dueDate": 2}]}
    GOOD = """window.__fetchOrder = async id => ({d: JSON.parse(JSON.stringify(STATE)), e: []});
      window.__updOrder = async (id, patch) => { Object.assign(STATE, JSON.parse(JSON.stringify(patch))); return {err: [], data: {}}; };"""

    def run_js(self, plan, mock=None, state=None):
        js = events.make_js({"orders": plan})
        h = "globalThis.window={}; let STATE=%s; %s\n(%s).then(r=>console.log(JSON.stringify({r, STATE})))" % (json.dumps(state or self.BASE), mock or self.GOOD, js)
        o = subprocess.run(["node", "-e", h], capture_output=True, text=True, timeout=30)
        self.assertEqual(o.returncode, 0, o.stderr)
        d = json.loads(o.stdout.strip().splitlines()[-1]); return d["r"], d["STATE"]

    def pl(self, **kw):
        base = {"id": "O28", "title": "PO-T", "orderNumber": 28, "lines": [{"marker": "aaaaaaaa", "text": "[2026-10-12 18:00 ev:aaaaaaaa] SCHEDULE: ETD neu (Mail m1)", "type": "SCHEDULE", "mail_date": "2026-10-12 18:00"}],
                "date_patch": {}, "date_mail": "", "pay": []}
        base.update(kw); return [base]

    def test_notiz_wird_angehaengt_ohne_den_rest_zu_veraendern(self):
        r, st = self.run_js(self.pl()); self.assertTrue(r[0]["dataUnchanged"] and r[0]["notesOk"], r)
        self.assertEqual(st["notes"], "Quelle: PI.\n[2026-10-12 18:00 ev:aaaaaaaa] SCHEDULE: ETD neu (Mail m1)")

    def test_wiederholung_haengt_nichts_doppelt_an(self):
        r, st = self.run_js(self.pl(), state=dict(self.BASE, notes="x\n[2026-10-12 18:00 ev:aaaaaaaa] SCHEDULE: ETD neu (Mail m1)"))
        self.assertTrue(r[0]["unchanged"])

    def test_datum_wird_gesetzt(self):
        r, st = self.run_js(self.pl(date_patch={"etdEstimatedDate": "2026-10-15T00:00:00.000Z"}, date_mail="2026-10-12 18:00"))
        self.assertEqual(r[0]["dates"], ["etdEstimatedDate"]); self.assertTrue(r[0]["datesOk"]); self.assertEqual(st["etdEstimatedDate"], "2026-10-15T00:00:00.000Z")

    def test_aelteres_datum_ueberschreibt_neueren_eintrag_nicht(self):
        notes = "[2026-10-14 08:00 ev:bbbbbbbb] SCHEDULE: ETD 30.10. (Mail m9)"
        r, st = self.run_js(self.pl(date_patch={"etdEstimatedDate": "2026-10-15T00:00:00.000Z"}, date_mail="2026-10-12 18:00"), state=dict(self.BASE, notes=notes))
        self.assertEqual(r[0]["dates"], []); self.assertEqual(st["etdEstimatedDate"], 1790000000000)

    def test_zahlung_eindeutig_wird_paid(self):
        r, st = self.run_js(self.pl(pay=[{"amount": 30.0, "marker": "aaaaaaaa"}]))
        self.assertEqual(r[0]["paymentsMarkedPaid"], 1); self.assertTrue(r[0]["dataUnchanged"]); self.assertEqual([p["status"] for p in st["payments"]], ["Paid", "Unpaid"])

    def test_zahlung_mehrdeutig_oder_unbekannt_wird_nicht_angefasst(self):
        two = dict(self.BASE, payments=[{"name": "a", "status": "Unpaid", "amount": 30, "dueDate": 1}, {"name": "b", "status": "Unpaid", "amount": 30, "dueDate": 2}])
        r, st = self.run_js(self.pl(pay=[{"amount": 30.0, "marker": "x"}]), state=two); self.assertEqual(r[0]["paymentsMarkedPaid"], 0)
        r, st = self.run_js(self.pl(pay=[{"amount": 99.0, "marker": "x"}])); self.assertEqual(r[0]["paymentsMarkedPaid"], 0)

    def test_schon_bezahlte_zahlung_wird_nicht_nochmal_gezaehlt(self):
        paid = dict(self.BASE, payments=[{"name": "a", "status": "Paid", "amount": 30, "dueDate": 1}, {"name": "b", "status": "Unpaid", "amount": 70, "dueDate": 2}])
        r, _ = self.run_js(self.pl(pay=[{"amount": 30.0, "marker": "x"}]), state=paid); self.assertEqual(r[0]["paymentsMarkedPaid"], 0)

    def test_abbruch_wenn_update_positionen_veraendert(self):
        mock = self.GOOD.replace("Object.assign(STATE, JSON.parse(JSON.stringify(patch)));", "Object.assign(STATE, JSON.parse(JSON.stringify(patch))); STATE.items[0].variants[0].amounts[0].quantity = 99;")
        r, _ = self.run_js(self.pl(), mock=mock); self.assertFalse(r[0]["dataUnchanged"]); self.assertIn("ABBRUCH", r[0])

    def test_abbruch_wenn_produktlink_verloren_geht(self):
        mock = self.GOOD.replace("Object.assign(STATE, JSON.parse(JSON.stringify(patch)));", "Object.assign(STATE, JSON.parse(JSON.stringify(patch))); STATE.items[0].product = null;")
        r, _ = self.run_js(self.pl(), mock=mock); self.assertFalse(r[0]["dataUnchanged"]); self.assertIn("ABBRUCH", r[0])

    def test_abbruch_wenn_notiz_nicht_gespeichert(self):
        mock = self.GOOD.replace("Object.assign(STATE, JSON.parse(JSON.stringify(patch)));", "")
        r, _ = self.run_js(self.pl(), mock=mock); self.assertFalse(r[0]["notesOk"]); self.assertIn("ABBRUCH", r[0])

    def test_fehler_stoppt_und_meldet_unsicher(self):
        mock = "window.__fetchOrder = async id => ({d: JSON.parse(JSON.stringify(STATE)), e: []}); window.__updOrder = async () => ({err: ['kaputt']});"
        r, _ = self.run_js(self.pl(), mock=mock); self.assertTrue(r[0]["unsure"])

    def test_helfer_fehlen(self):
        r, _ = self.run_js(self.pl(), mock="window.__fetchOrder = undefined;"); self.assertIn("fatal", r[0])

    def test_zweite_order_wird_nach_fehler_nicht_angefasst(self):
        mock = "let n=0; window.__fetchOrder = async id => ({d: JSON.parse(JSON.stringify(STATE)), e: []}); window.__updOrder = async () => ({err: ['kaputt']});"
        plan = self.pl() + [dict(self.pl()[0], id="O2", title="PO-2")]
        r, _ = self.run_js(plan, mock=mock); self.assertEqual(len(r), 1)


if __name__ == "__main__":
    unittest.main()


class ZuordnungVerbesserungen1910(unittest.TestCase):
    """19.10.: Fehlzuordnungen aus dem Rueckstand (Kennungslisten, Style als PO-Nr, Testobjekte, tuerkische Namen, Absender-Domain)."""
    V = [{"id": "v1", "name": "Xiamen Lieferant G Industry Co., Ltd", "contacts": [{"email": "kontakt@lieferant-g.example"}]},
         {"id": "v2", "name": "Lieferant AG"}, {"id": "v3", "name": "Ningbo Lieferant D Co., Ltd"}]
    O = [{"id": "o1", "title": "PO-LIEFERANT_G-MC-26SM002", "manufacturer": {"id": "v1"}, "items": [{"name": "GT0303 Sport Travel Bag"}], "status": {"status": "In Production"}},
         {"id": "o2", "title": "PO-LIEFERANT_D-ALI20260821", "manufacturer": {"id": "v3"}, "items": [{"name": "F-3 Fleece Kenna Jacket"}], "status": {"status": "In Transit"}},
         {"id": "o3", "title": "PO-LIEFERANT_D-T1", "manufacturer": {"id": "v3"}, "items": [{"name": "F-3 Fleece Kenna Jacket"}], "status": {"status": "In Transit"}},
         {"id": "o4", "title": "PO-LIEFERANT_AG-2026-06-24", "manufacturer": {"id": "v2"}, "items": [{"name": "YK-002 Pants"}], "status": {"status": "In Production"}}]

    def e(self, **kw):
        d = {"type": "SHIPMENT", "vendor": None, "ref": {"po_number": None, "style": None, "container": None}, "date": "2026-10-12", "summary": "x", "key": "k", "_mail": {"id": "m", "date": "2026-10-12 10:00", "from": "kontakt@firma.example", "subject": "s"}}
        d.update(kw); return d

    def test_kennungsliste_und_klammern_werden_zerlegt(self):
        o, why = events.find_order(self.e(ref={"po_number": "26022(GT0303)", "style": None, "container": None}), self.O, self.V)
        self.assertEqual((o or {}).get("id"), "o1", why)
        o, why = events.find_order(self.e(ref={"po_number": None, "style": "GT0301, GT0303", "container": None}), self.O, self.V)
        self.assertEqual((o or {}).get("id"), "o1", why)

    def test_testobjekte_erzeugen_keine_mehrdeutigkeit(self):
        pl = events.plan([self.e(ref={"po_number": None, "style": "fleece kenna jacket", "container": None})], self.O, self.V)
        self.assertEqual([p["id"] for p in pl["orders"]], ["o2"])

    def test_tuerkischer_lieferantenname(self):
        self.assertEqual((events.vendor_of(self.e(vendor="LIEFERANT_AG"), self.V) or {}).get("id"), "v2")

    def test_lieferant_ueber_absender_domain(self):
        dom = events.domain_vendors(self.V)
        self.assertEqual((events.vendor_of(self.e(_mail={"from": "Wendy <kontakt@lieferant-g.example>"}), self.V, None, dom) or {}).get("id"), "v1")
        self.assertIsNone(events.vendor_of(self.e(_mail={"from": "kontakt@firma.example"}), self.V, None, dom))

    def test_kurze_belegnummer_zaehlt_als_kennung(self):
        self.assertIn("ak62326", events.id_tokens("Rechnung AK/623/26"))
