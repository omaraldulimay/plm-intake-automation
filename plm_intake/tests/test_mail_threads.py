import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import events, mail_threads, zuordnung  # noqa: E402

V = [{"id": "VA", "name": "Lieferant A"}, {"id": "VC", "name": "Lieferant D"}]
O = [{"id": "C1", "title": "PO-LIEFERANT_D-1", "manufacturer": {"id": "VC"}, "status": {"status": "In Production"}, "items": []},
     {"id": "C2", "title": "PO-LIEFERANT_D-2", "manufacturer": {"id": "VC"}, "status": {"status": "Approved"}, "items": []},
     {"id": "A1", "title": "PO-ALPHA-1", "manufacturer": {"id": "VA"}, "status": {"status": "In Production"}, "items": []},
     {"id": "A2", "title": "PO-ALPHA-2", "manufacturer": {"id": "VA"}, "status": {"status": "Approved"}, "items": []}]


def e(mid, thread, po=None, key=None, vendor="Lieferant D", **kw):
    x = {"type": "SHIPMENT", "vendor": vendor, "ref": {"po_number": po, "style": None, "container": None}, "date": None, "summary": "Verladung %s" % mid, "details": {}, "confidence": 0.9,
         "key": key or mid, "_mail": {"id": mid, "date": "2026-10-15 10:%s" % mid[-2:].rjust(2, "0"), "from": "kontakt@lieferant-d.example", "subject": "s", "thread": thread}}
    x.update(kw); return x


def run(evs, **kw):
    with mock.patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "THREAD_MATCH"}, clear=True):
        if "env" in kw:
            os.environ.update(kw.pop("env"))
        return events.plan(evs, O, V, {}, {}, vendor_only=True, **kw)


def assigned(pl):
    return {l["marker"]: o["id"] for o in pl["orders"] for l in o["lines"]}


class Verlauf(unittest.TestCase):
    def setUp(self):
        self.beleg = e("m01", "T1", po="PO-LIEFERANT_D-1")   # sicher zu C1
        self.offen = e("m02", "T1")                   # ohne Bezug: mehrdeutig (2 laufende Orders von Lieferant D)

    def test_basis_ohne_verlauf_ist_offen(self):
        pl = run([self.beleg, e("m02", None)])
        self.assertEqual(len(pl["unmatched"]), 1); self.assertIn("mehrdeutig", pl["unmatched"][0]["reason"])

    def test_verlauf_eindeutig_zugeordnet(self):
        pl = run([self.beleg, self.offen])
        self.assertEqual(pl["unmatched"], [])
        self.assertEqual(assigned(pl)[events.marker(self.offen)], "C1")
        ln = next(l for o in pl["orders"] for l in o["lines"] if l["marker"] == events.marker(self.offen))
        self.assertIn("ueber Mail-Verlauf zugeordnet", ln["text"]); self.assertTrue(ln["weak"])
        p = pl["orders"][0]
        self.assertEqual(p["date_patch"], {}); self.assertEqual(p["pay"], [])   # nur Notiz

    def test_verlauf_mehrdeutig_bleibt_offen(self):
        pl = run([self.beleg, e("m03", "T1", po="PO-LIEFERANT_D-2"), self.offen])
        self.assertEqual([u["event"]["_mail"]["id"] for u in pl["unmatched"]], ["m02"])

    def test_lieferant_passt_nicht_bleibt_offen(self):
        fremd = e("m02", "T1", vendor="Lieferant A")   # Alpha hat 2 laufende Orders -> mehrdeutig, Verlauf zeigt aber auf Lieferant D
        pl = run([self.beleg, fremd])
        self.assertEqual([u["event"]["_mail"]["id"] for u in pl["unmatched"]], ["m02"])

    def test_verlauf_mit_mehreren_lieferanten_bleibt_offen(self):   # Fall Gmail-Verlauf mit 5 Lieferanten: Orders verschiedener Lieferanten = mehrdeutig
        pl = run([self.beleg, e("m03", "T1", po="PO-ALPHA-1", vendor="Lieferant A"), self.offen])
        self.assertEqual([u["event"]["_mail"]["id"] for u in pl["unmatched"]], ["m02"])

    def test_schalter_aus_unveraendert(self):
        pl = run([self.beleg, self.offen], env={"THREAD_MATCH": "0"})
        self.assertEqual([u["event"]["_mail"]["id"] for u in pl["unmatched"]], ["m02"])

    def test_thread_unbekannt_unveraendert(self):
        for t in (None, "T_ANDERS"):
            pl = run([self.beleg, e("m02", t)])
            self.assertEqual([u["event"]["_mail"]["id"] for u in pl["unmatched"]], ["m02"])

    def test_gespeicherter_stand_zaehlt(self):   # Beleg-Ereignis liegt nicht mehr in der Inbox, nur der gelernte Stand
        pl = run([self.offen], thread_orders={"T1": ["C1"]})
        self.assertEqual(assigned(pl)[events.marker(self.offen)], "C1")
        pl = run([self.offen], thread_orders={"T1": ["C1", "C2"]})
        self.assertEqual(len(pl["unmatched"]), 1)
        pl = run([self.offen], thread_orders={"T1": ["GELOESCHT"]})
        self.assertEqual(len(pl["unmatched"]), 1)

    def test_geerbtes_wird_nicht_gelernt(self):
        pl = run([self.beleg, self.offen])
        st = {}
        mail_threads.learn(st, pl["assigned"])
        self.assertEqual(st, {"T1": ["C1"]})

    def test_info_und_abweichend_werden_nicht_ueberschrieben(self):
        i = e("m04", "T1", type="SAMPLE")   # Muster ohne PO: Info, kein Verlaufs-Erbe
        pl = run([self.beleg, i])
        self.assertEqual(assigned(pl).get(events.marker(i)), None)


class Zustand(unittest.TestCase):
    def test_learn_save_load(self):
        st = {}
        a = [(e("m1", "T1"), "C1", "ok"), (e("m2", "T1"), "C1", "po_id"), (e("m3", "T2"), "C2", "vendor_only"), (e("m4", None), "C1", "ok"), (e("m5", "T3"), "C2", "klaerung"), (e("m6", "T4"), "C2", "thread")]
        self.assertEqual(mail_threads.learn(st, a), 3)   # eigene (auch schwache) Zuordnungen zaehlen, geerbte nie, ohne Thread nichts
        self.assertEqual(st, {"T1": ["C1"], "T2": ["C2"], "T3": ["C2"]})
        d = Path(tempfile.mkdtemp()) / "mail_threads.json"
        mail_threads.save(d, st); self.assertEqual(mail_threads.load(d), st)
        self.assertEqual(mail_threads.load(d.parent / "gibtsnicht.json"), {})

    def test_load_events_uebernimmt_thread_id(self):
        d = Path(tempfile.mkdtemp())
        (d / "a_events.json").write_text(json.dumps({"mail_id": "a", "mail_date": "2026-10-01 10:00", "from": "x", "subject": "s", "thread_id": "T9", "events": [{"type": "OTHER"}]}))
        (d / "b_events.json").write_text(json.dumps({"mail_id": "b", "mail_date": "2026-10-01 10:00", "from": "x", "subject": "s", "events": [{"type": "OTHER"}]}))
        ev = events.load_events(sorted(d.glob("*_events.json")))
        self.assertEqual([x["_mail"]["thread"] for x in ev], ["T9", None])

    def test_state_file_in_cloud(self):
        from plm_intake import cloud
        self.assertIn("intake/mail_threads.json", cloud.STATE_FILES)


class ZuordnungTabelle(unittest.TestCase):
    def row(self, i, mk, zu="", mail="m1"):
        return {"id": i, "values": {"Quelle": "x | ev:" + mk, "Zuordnung": zu, "Mail-ID": mail, "Status": "offen"}}

    def test_thread_mit_gleichem_lieferanten_geht_mit(self):
        evs = {"aaaaaaaa": e("m1", "T1"), "bbbbbbbb": e("m2", "T1"), "cccccccc": e("m3", "T1", vendor="Lieferant A"), "dddddddd": e("m4", "T2")}
        rows = [self.row("r1", "aaaaaaaa", "PO-LIEFERANT_D-1"), self.row("r2", "bbbbbbbb", mail="m2"), self.row("r3", "cccccccc", mail="m3"), self.row("r4", "dddddddd", mail="m4")]
        p = zuordnung.plan(rows, O, {}, {}, evs)
        self.assertEqual(p["ev_ov"], {"aaaaaaaa": "C1", "bbbbbbbb": "C1"})
        p = zuordnung.plan([self.row("r1", "aaaaaaaa", "PO-LIEFERANT_D-1 !nur")] + rows[1:], O, {}, {}, evs)
        self.assertEqual(p["ev_ov"], {"aaaaaaaa": "C1"})
        p = zuordnung.plan(rows[:2], O, {}, {}, {})   # Thread unbekannt: nur die eigene Zeile
        self.assertEqual(p["ev_ov"], {"aaaaaaaa": "C1"})
        rows[0]["values"]["Zuordnung"] = "info"
        p = zuordnung.plan(rows, O, {}, {}, evs)
        self.assertEqual(p["ev_ov"], {"aaaaaaaa": events.INFO_OVERRIDE})   # info geht nie ueber den Verlauf


if __name__ == "__main__":
    unittest.main()
