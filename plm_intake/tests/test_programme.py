"""Programm-/Mehrfach-Zuordnung (plm_intake.programme), Nummern-Kette (Betreffnummer/Positionswort) und Info-Regel (events.plan)."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import events, klaerfaelle, programme  # noqa: E402

V = [{"id": "VA", "name": "Lieferant A"}, {"id": "VT", "name": "Lieferant B Enterprises"}, {"id": "VC", "name": "Lieferant D"}, {"id": "VF", "name": "Lieferant H"},
     {"id": "VW", "name": "Lieferant C"}, {"id": "VN", "name": "Nirgends Trading"}]


def order(i, title, vid, status="In Production", items=(), po=None):
    return {"id": i, "title": title, "orderNumber": int(i[1:]) if i[1:].isdigit() else 0, "manufacturer": {"id": vid}, "status": {"status": status}, "poNumber": po,
            "items": [{"name": n} for n in items]}


O = [order("A1", "PO-ALPHA-KUNDE_X-DE", "VA"), order("A2", "PO-ALPHA-KUNDE_X-CH", "VA"), order("A3", "PO-ALPHA-KUNDE_X-LAGER", "VA"), order("A4", "PO-ALPHA-SWEAT", "VA"),
     order("A5", "PO-ALPHA-KUNDE_X-OLD", "VA", status="Complete"),
     order("T1", "PO-LIEFERANT_B-BASIC", "VT", items=["BASIC T-SHIRT 180 GSM", "BLACK FRIDAY HOODIE 360 GSM"]), order("T2", "PO-LIEFERANT_B-SOCKS", "VT", items=["Tennissocks White"]),
     order("C1", "PO-LIEFERANT_D-1", "VC"), order("F1", "PO-LIEFERANT_H-RAINJACKET", "VF", po="F260526SF"),
     order("W1", "PO-WONDERS-A", "VW", items=["XW-042 Rain Jacket Crocodile"]), order("W2", "PO-WONDERS-B", "VW", items=["XW-042 Rain Jacket Chettah (Cheetah)", "XW-042 Rain Jacket Crocodile"])]
CFG = {"programme": {"KUNDE_X Alpha": {"lieferanten": ["Lieferant A"], "woerter": ["kunde_x"], "kennungen": ["561874", "AK/626/26"],
                                    "orders": ["PO-ALPHA-KUNDE_X-DE", "PO-ALPHA-KUNDE_X-CH", "PO-ALPHA-KUNDE_X-LAGER", "PO-ALPHA-KUNDE_X-OLD"],
                                    "container": {"EGHU9143480": ["PO-ALPHA-KUNDE_X-DE", "PO-ALPHA-KUNDE_X-CH"]}},
                     "Wonders XW-042": {"lieferanten": ["Lieferant C"], "woerter": [], "kennungen": ["XW-042"], "orders": ["PO-WONDERS-A", "PO-WONDERS-B"]}},
       "andere_woerter": ["kunde_y", "sweat"]}


def e(mid, summary="Termin", vendor="Lieferant A", typ="SCHEDULE", thread=None, subject="s", ref=None, details=None, quote="", frm="kontakt@lieferant-a.example", date="2026-10-20 10:%s"):
    return {"type": typ, "vendor": vendor, "ref": ref or {"po_number": None, "style": None, "container": None}, "date": None, "summary": summary, "source_quote": quote, "details": details or {},
            "confidence": 0.9, "key": mid, "_mail": {"id": mid, "date": date % mid[-2:].rjust(2, "0"), "from": frm, "subject": subject, "thread": thread}}


def run(evs, orders=None, cfg=CFG, env=None, **kw):
    base = {k: v for k, v in os.environ.items() if k not in ("PROGRAMM_MATCH", "NUMMER_MATCH", "INFO_REGEL", "THREAD_MATCH")}
    with mock.patch.dict(os.environ, {**base, **(env or {})}, clear=True):
        return events.plan(evs, orders or O, V, {}, {}, vendor_only=True, programme_cfg=cfg, **kw)


def where(pl):
    out = {}
    for o in pl["orders"]:
        for ln in o["lines"]:
            out.setdefault(ln["marker"], set()).add(o["id"])
    return out


def reasons(pl):
    return {u["event"]["_mail"]["id"]: u["reason"] for u in pl["unmatched"]}


class Programm(unittest.TestCase):
    def test_eindeutig_notiz_in_alle_orders_der_gruppe(self):
        x = e("m01", "Zeitplan fuer das KUNDE_X-Polyester-Programm: Ex Factory 30.10.", details={"new_ex_factory": "2026-10-30"})
        pl = run([x])
        self.assertEqual(pl["unmatched"], [])
        self.assertEqual(where(pl)[events.marker(x)], {"A1", "A2", "A3"})   # Complete-Order A5 gehoert nicht dazu
        for p in pl["orders"]:
            self.assertEqual(p["date_patch"], {}); self.assertEqual(p["pay"], []); self.assertNotIn("ship", p); self.assertNotIn("status", p)
            ln = p["lines"][0]
            self.assertTrue(ln["weak"]); self.assertIn("ueber Programm KUNDE_X Alpha zugeordnet", ln["text"]); self.assertIn("Notiz in allen 3 Orders", ln["text"])
        self.assertEqual(pl["stats"]["programm"], 1)

    def test_ian_und_rechnungsnummer_im_text(self):
        for kw in ({"ref": {"po_number": None, "style": "561874_2510", "container": None}}, {"details": {"invoice_number": "AK/626/26"}}, {"quote": "Rechnung AK-626-26 liegt vor"}):
            pl = run([e("m02", "Containerpapiere ausgestellt", typ="SHIPMENT", **kw)])
            self.assertEqual(pl["unmatched"], [], kw)
            self.assertEqual(len(pl["orders"]), 3)

    def test_ian_nicht_als_teil_einer_laengeren_zahl(self):
        pl = run([e("m03", "Menge 5618749 Stk")])
        self.assertEqual(len(pl["unmatched"]), 1)

    def test_container_nur_teil_der_gruppe(self):
        pl = run([e("m04", "Container wurde entladen (KUNDE_X)", typ="SHIPMENT", ref={"po_number": None, "style": None, "container": "EGHU 914 348-0"})])
        self.assertEqual({p["id"] for p in pl["orders"]}, {"A1", "A2"})

    def test_zwei_programme_oder_fremdwort_im_text_bleibt_offen(self):
        pl = run([e("m05", "Status fuer KUNDE_X und Kunde Y Q2 bitte")])
        self.assertEqual(len(pl["unmatched"]), 1); self.assertEqual(pl["orders"], [])
        pl = run([e("m06", "KUNDE_X Polyester und Sweat Styles: Luftfracht 4. Charge")])
        self.assertEqual(len(pl["unmatched"]), 1)

    def test_schalter_aus_unveraendert(self):
        pl = run([e("m07", "KUNDE_X Polyester Zeitplan")], env={"PROGRAMM_MATCH": "0"})
        self.assertEqual(len(pl["unmatched"]), 1); self.assertEqual(pl["orders"], [])

    def test_lieferant_passt_nicht_oder_fehlt(self):
        pl = run([e("m08", "KUNDE_X Socken Ankunft", vendor="Lieferant D", typ="SHIPMENT")])   # Lieferant D hat nur 1 Order -> vendor_only, aber nie eine Alpha-Gruppe
        self.assertEqual({p["id"] for p in pl["orders"]}, {"C1"})   # alte Regel (einzige laufende Order), nicht das Programm
        self.assertTrue(all("Programm" not in ln["text"] for p in pl["orders"] for ln in p["lines"]))
        pl = run([e("m09", "KUNDE_X Polyester Zeitplan", vendor=None, frm="kontakt@example.com")])
        self.assertEqual(len(pl["unmatched"]), 1)
        pl = run([e("m10", "KUNDE_X Polyester Zeitplan", vendor="Lieferant B Enterprises")])
        self.assertTrue(all("Programm" not in ln["text"] for p in pl["orders"] for ln in p["lines"]))

    def test_betreff_nur_ohne_andere_programme(self):
        pl = run([e("m11", "Container entladen", typ="SHIPMENT", subject="Karachi Container fuer KUNDE_X Aktion")])
        self.assertEqual(len(pl["orders"]), 3)
        pl = run([e("m12", "Container entladen", typ="SHIPMENT", subject="Status Update - KUNDE_X / Kunde Y Q2 2027 / XTRAFIT")])
        self.assertEqual(len(pl["unmatched"]), 1)
        pl = run([e("m13", "Ex-Factory Zeitplan bestaetigt", subject="KUNDE_X x Smilodox")])   # Text nennt kein Programmwort, Betreff schon
        self.assertEqual(len(pl["orders"]), 3)
        pl = run([e("m13", "Zeitplan fuer Kunde Y Black Friday", subject="KUNDE_X x Smilodox")])   # Text nennt ein FREMDES Programm: nichts
        self.assertEqual(len(pl["unmatched"]), 1)

    def test_zahlung_nur_notiz(self):
        pl = run([e("m14", "KUNDE_X Anzahlung bezahlt", typ="PAYMENT", details={"paid": True, "amount": 1000})])
        self.assertEqual(len(pl["orders"]), 3)
        for p in pl["orders"]:
            self.assertEqual(p["pay"], [])

    def test_programm_geht_vor_dem_verlauf(self):   # Fall ev:53bb666d: KUNDE_X-Ereignis im gemischten Verlauf erbte die Sweat-Order
        beleg = e("m15", "Sweat Styles Luftfracht", ref={"po_number": "PO-ALPHA-SWEAT", "style": None, "container": None}, thread="T1", subject="Daily Meeting Summary 21.10.")
        kunde_x = e("m16", "KUNDE_X Polyester: Ex-mill 30.10.", thread="T1", subject="Daily Meeting Summary 21.10.")
        pl = run([beleg, kunde_x])
        w = where(pl)
        self.assertEqual(w[events.marker(kunde_x)], {"A1", "A2", "A3"}); self.assertEqual(w[events.marker(beleg)], {"A4"})
        pl = run([beleg, kunde_x], env={"PROGRAMM_MATCH": "0"})   # ohne Schalter: alter Fehler (erbt Sweat) bleibt erhalten, ist hier nur der Beleg fuer den Unterschied
        self.assertEqual(where(pl)[events.marker(kunde_x)], {"A4"})

    def test_verlauf_erbt_nur_bei_einem_programm(self):
        a, b = e("m17", "KUNDE_X Polyester Zeitplan", thread="T2"), e("m18", "KUNDE_X Polystyles bestaetigt", thread="T2")
        plain = e("m19", "Ex-factory morgen, 32.000 Stk", thread="T2")
        pl = run([a, b, plain])
        self.assertEqual(pl["unmatched"], []); self.assertEqual(where(pl)[events.marker(plain)], {"A1", "A2", "A3"})
        self.assertIn("Gmail-Verlauf", [ln["text"] for p in pl["orders"] for ln in p["lines"] if ln["marker"] == events.marker(plain)][0])
        pl = run([a, plain])   # nur EIN Treffer im Verlauf: zu wenig
        self.assertEqual([u["event"]["_mail"]["id"] for u in pl["unmatched"]], ["m19"])
        sweat = e("m20", "Sweat Luftfracht", ref={"po_number": "PO-ALPHA-SWEAT", "style": None, "container": None}, thread="T2")
        pl = run([a, b, plain, sweat])   # gemischter Verlauf (eine fremde Order): erben verboten
        self.assertEqual([u["event"]["_mail"]["id"] for u in pl["unmatched"]], ["m19"])
        fremd = e("m21", "Kunde Y Zeitplan, KUNDE_X ebenfalls", thread="T2")
        pl = run([a, b, plain, fremd])   # Fremdwort in einem Ereignis des Verlaufs
        self.assertIn("m19", [u["event"]["_mail"]["id"] for u in pl["unmatched"]])

    def test_konkreter_hinweis_geht_vor(self):   # Ereignis nennt PO-Nr einer anderen Alpha-Order: find_order-Ergebnis gilt, kein Programm
        x = e("m22", "KUNDE_X Zeitplan", ref={"po_number": "PO-ALPHA-SWEAT", "style": None, "container": None})
        pl = run([x])
        self.assertEqual(where(pl)[events.marker(x)], {"A4"})

    def test_alle_orders_complete_keine_zuordnung(self):
        o2 = [o for o in O if o["id"] not in ("A1", "A2", "A3")]
        pl = run([e("m23", "KUNDE_X Zeitplan")], orders=o2)
        self.assertEqual(len([p for p in pl["orders"] if "Programm" in p["lines"][0]["text"]]), 0)

    def test_marker_je_order_eindeutig_und_wiederholbar(self):
        x = e("m24", "KUNDE_X Zeitplan")
        pl = run([x, dict(x)])   # Doppel-Ereignis (gleicher Marker)
        for p in pl["orders"]:
            self.assertEqual([ln["marker"] for ln in p["lines"]], [events.marker(x)])
        self.assertEqual(run([x])["orders"][0]["lines"][0]["text"], pl["orders"][0]["lines"][0]["text"])   # gleicher Text: der Marker verhindert doppelte Notizen im PLM

    def test_start_datei_und_fallback(self):
        cfg = programme.load("/nicht/vorhanden/programme.json")
        self.assertIn("KUNDE_X Alpha", cfg["programme"])
        self.assertTrue(all(p.get("orders") and p.get("lieferanten") for p in cfg["programme"].values()))
        self.assertEqual(programme.load("/nicht/vorhanden"), cfg)
        from plm_intake import cloud
        self.assertIn("intake/programme.json", cloud.STATE_FILES)   # Gruppen sind Zustand (wie po_aliases.json)


class Nummer(unittest.TestCase):
    def test_betreffnummer_ist_ponumber(self):
        x = e("n01", "Bill of Lading ausgestellt", vendor="Lieferant H", typ="SHIPMENT", subject="shipping docs for our inv. no.: F260526SF BY SEA", ref={"po_number": None, "style": "EISU9417382", "container": "40HC"})
        pl = run([x])
        self.assertEqual(where(pl)[events.marker(x)], {"F1"})
        ln = pl["orders"][0]["lines"][0]
        self.assertTrue(ln["weak"]); self.assertIn("Betreffnummer F260526SF", ln["text"]); self.assertEqual(pl["stats"]["nummer"], 1)

    def test_lieferant_passt_nicht_oder_schalter_aus(self):
        x = e("n02", "Versand", vendor="Lieferant D", typ="SHIPMENT", subject="inv. no.: F260526SF", ref={"po_number": None, "style": "X123456", "container": None})
        pl = run([x])
        self.assertTrue(all(p["id"] != "F1" for p in pl["orders"]))
        y = e("n03", "Versand", vendor="Lieferant H", typ="SHIPMENT", subject="inv. no.: F260526SF", ref={"po_number": None, "style": "X123456", "container": None})
        self.assertEqual(len(run([y], env={"NUMMER_MATCH": "0"})["unmatched"]), 1)

    def test_zwei_orders_gleiche_nummer_bleibt_offen(self):
        o2 = O + [order("F2", "PO-LIEFERANT_H-2", "VF", po="F260526SF")]
        y = e("n04", "Versand", vendor="Lieferant H", typ="SHIPMENT", subject="inv. no.: F260526SF", ref={"po_number": None, "style": "X123456", "container": None})
        self.assertEqual(len(run([y], orders=o2)["unmatched"]), 1)

    def test_positionswort_zweiwort_und_tippfehler(self):
        x = e("n05", "Shipment documents of Black Friday goods", vendor="Lieferant B Enterprises", typ="SHIPMENT")
        pl = run([x])
        self.assertEqual(where(pl)[events.marker(x)], {"T1"}); self.assertIn("Positionswort", pl["orders"][0]["lines"][0]["text"])
        y = e("n06", "Cheetah Print Barcodes bestaetigt", vendor="Lieferant C", typ="ORDER_CHANGE")
        self.assertEqual(where(run([y]))[events.marker(y)], {"W2"})
        z = e("n07", "Chetta Print Barcodes bestaetigt", vendor="Lieferant C", typ="ORDER_CHANGE")   # Tippfehler
        self.assertEqual(where(run([z]))[events.marker(z)], {"W2"})

    def test_positionswort_in_zwei_orders_oder_nur_fuellwoerter_bleibt_offen(self):
        x = e("n08", "Crocodile Print Barcodes bestaetigt", vendor="Lieferant C", typ="ORDER_CHANGE")
        cfg = {"programme": {}}   # ohne Programm-Gruppe: Crocodile steht in beiden Orders -> nichts
        self.assertEqual(len(run([x], cfg=cfg)["unmatched"]), 1)
        both = e("n09", "Cheetah und Crocodile Print: Style-Nummern bestaetigt", vendor="Lieferant C", typ="ORDER_CHANGE")   # Cheetah nur W2, Crocodile in beiden: nicht nur W2
        self.assertEqual(len(run([both], cfg=cfg)["unmatched"]), 1)
        w = e("n10", "Black jacket delivery on Friday", vendor="Lieferant B Enterprises", typ="SHIPMENT")   # Farbe/Kleidung/Wochentag zaehlen nicht
        self.assertEqual(len(run([w])["unmatched"]), 1)

    def test_wonders_mix_geht_ueber_programm_beide_orders(self):
        both = e("n11", "Cheetah und Crocodile Print: Style-Nummern XW-042 bestaetigt", vendor="Lieferant C", typ="ORDER_CHANGE")
        pl = run([both])
        self.assertEqual(where(pl)[events.marker(both)], {"W1", "W2"})


class InfoRegel(unittest.TestCase):
    def test_gestrichener_style_ohne_order(self):
        x = e("i01", "Cancellation of styles FAB-001 and FAB-002.", vendor="Lieferant B Enterprises", typ="ORDER_CHANGE", ref={"po_number": None, "style": "FAB-001, FAB-002", "container": None})
        pl = run([x])
        self.assertEqual(pl["orders"], []); self.assertTrue(reasons(pl)["i01"].startswith(events.INFO_TAG)); self.assertEqual(pl["stats"]["info_regel"], 1)
        self.assertEqual(klaerfaelle.select(pl["unmatched"], V, {}, {}, {}, O), [])   # kein Klaerfall mehr

    def test_style_in_einer_order_bleibt_klaerfall(self):
        x = e("i02", "Cancellation of style XW-042.", vendor="Lieferant B Enterprises", typ="ORDER_CHANGE", ref={"po_number": None, "style": "XW-042", "container": None})
        self.assertFalse(reasons(run([x]))["i02"].startswith("info:"))

    def test_mit_po_rechnung_betrag_bleibt_klaerfall(self):
        for kw in ({"ref": {"po_number": "PO-NEU-99", "style": "FAB-001", "container": None}}, {"details": {"invoice_number": "INV-77"}}, {"details": {"amount": 100}}):
            x = e("i03", "Cancellation of styles FAB-001.", vendor="Lieferant B Enterprises", typ="ORDER_CHANGE", **kw)
            x.setdefault("ref", {"po_number": None, "style": "FAB-001", "container": None})
            if "ref" in kw:
                x["ref"] = kw["ref"]
            self.assertFalse(reasons(run([x])).get("i03", "").startswith("info:"), kw)
        y = e("i04", "Rechnung fuer FAB-001 ueberwiesen", vendor="Lieferant B Enterprises", typ="ORDER_CHANGE", ref={"po_number": None, "style": "FAB-001", "container": None})
        self.assertFalse(reasons(run([y])).get("i04", "").startswith("info:"))

    def test_lieferant_ohne_jede_order(self):
        x = e("i05", "New samples were sent, development ongoing", vendor="Nirgends Trading", typ="SAMPLE")
        self.assertTrue(reasons(run([x]))["i05"].startswith("info:"))
        y = e("i06", "Sample development: schedule update", vendor="Lieferant B Enterprises", typ="SCHEDULE")   # Lieferant HAT Orders, kein Style: bleibt Klaerfall (mehrdeutig)
        self.assertTrue(reasons(run([y]))["i06"].startswith("mehrdeutig"))

    def test_zahlung_versand_termin_ohne_thema_bleibt_klaerfall(self):
        for typ in ("PAYMENT", "SHIPMENT", "SCHEDULE"):
            x = e("i07", "Ware wird verladen", vendor="Nirgends Trading", typ=typ)
            self.assertFalse(reasons(run([x])).get("i07", "").startswith("info:"), typ)
        z = e("i08", "Zahlung fuer Styles ZZ-123 eingegangen", vendor="Nirgends Trading", typ="ORDER_CHANGE")
        self.assertFalse(reasons(run([z])).get("i08", "").startswith("info:"))

    def test_schalter_aus(self):
        x = e("i09", "Cancellation of styles FAB-001.", vendor="Lieferant B Enterprises", typ="ORDER_CHANGE", ref={"po_number": None, "style": "FAB-001", "container": None})
        self.assertFalse(reasons(run([x], env={"INFO_REGEL": "0"}))["i09"].startswith("info:"))

    def test_datumsreste_sind_keine_styles(self):
        x = e("i10", "Request for confirmation of dates by 27.10.2026, sample status", vendor=None, typ="SCHEDULE", details={"x_date": "2026-11-05"}, quote="Please confirm 2026-11-05")
        self.assertFalse(reasons(run([x])).get("i10", "").startswith(events.INFO_TAG))


class Datenpflege(unittest.TestCase):
    def test_nur_zeilen_ohne_mail_quelle(self):
        zahl = {"Quelle": "Zahlungsplan 2026-10-26 | plan | ev:a81c4c74", "Warum offen": "Plan unveraendert"}
        mail = {"Quelle": "Mail 2026-10-20 10:00 | Betreff | ev:12345678", "Warum offen": "Passt zu mehreren Bestellungen"}
        self.assertTrue(klaerfaelle.ist_datenpflege(zahl)); self.assertFalse(klaerfaelle.ist_datenpflege(mail)); self.assertFalse(klaerfaelle.ist_datenpflege({}))
        self.assertEqual(klaerfaelle.datenpflege(zahl)["Warum offen"], "Datenpflege: Plan unveraendert")
        self.assertEqual(klaerfaelle.datenpflege(mail), mail)
        d = klaerfaelle.datenpflege(zahl)
        self.assertEqual(klaerfaelle.datenpflege(d)["Warum offen"], d["Warum offen"])   # nie doppelt
        self.assertEqual(zahl["Warum offen"], "Plan unveraendert")   # Eingabe unveraendert

    def test_neue_zahlungsplan_zeilen_beginnen_mit_datenpflege(self):
        from plm_intake import payments_plan
        r = payments_plan.klaer_row({"id": "x", "title": "PO-X"}, "Alpha", "plan", "Zahlungsplan pruefen: Summe", "Plan unveraendert", "pruefen", "2026-10-28")
        self.assertTrue(r["values"]["Warum offen"].startswith("Datenpflege: "))
        self.assertTrue(klaerfaelle.ist_datenpflege(r["values"]))


if __name__ == "__main__":
    unittest.main()
