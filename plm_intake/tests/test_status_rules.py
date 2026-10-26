import csv
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import status_apply as sa, status_rules as sr, tagesbericht as tb  # noqa: E402

TODAY = dt.date(2026, 10, 26)
ST = {n: {"id": "S" + n, "status": n, "color": "#000", "order": o} for n, o in sr.STATUS_ORDER.items()}


def order(i, status, pays=(), notes="", pieces=100, cost=1000, title=None):
    return {"id": i, "title": title or "PO-" + i, "orderNumber": 1, "status": ST[status], "payments": [{"name": "R%d" % k, "status": s, "amount": 1} for k, s in enumerate(pays)],
            "_notes": notes, "totalNumberOfPieces": pieces, "totalCost": cost}


def ship(oid, status, tracking="", qty=100):
    return {"id": "s" + oid + status, "title": "S " + oid, "status": status, "trackingNumber": tracking, "totalQuantity": qty, "products": [{"orderId": oid}]}


def ev(orders, ships=(), **kw):
    return {r["order_id"]: r for r in sr.evaluate(orders, list(ships), today=TODAY, **kw)}


class Rules(unittest.TestCase):
    def test_sendung_unterwegs_hoch(self):
        r = ev([order("A", "In Production")], [ship("A", "in_transit")])["A"]
        self.assertEqual((r["ziel"], r["sicherheit"], r["auto"]), ("In Transit", "hoch", True))

    def test_tracking_pending_mittel(self):
        r = ev([order("A", "Approved")], [ship("A", "pending", "123")])["A"]
        self.assertEqual((r["ziel"], r["sicherheit"], r["auto"]), ("In Transit", "mittel", False))
        self.assertNotIn("A", ev([order("A", "Approved")], [ship("A", "pending")]))   # ohne Tracking nichts

    def test_zahlung_paid_draft(self):
        r = ev([order("A", "Draft", ["Paid", "Unpaid"])])["A"]
        self.assertEqual((r["ziel"], r["regel"], r["sicherheit"]), ("Approved", "ZAHLUNG_PAID", "hoch"))
        self.assertNotIn("A", ev([order("B", "Approved", ["Paid"])]))   # nie auf gleicher Stufe

    def test_nie_nach_unten_nie_ab_complete(self):
        o = [order("A", "In Transit", ["Paid"]), order("B", "Complete", ["Paid"])]
        self.assertEqual(ev(o, [ship("A", "pending", "1")]), {})   # Approved/In Transit < In Transit: kein Vorschlag
        self.assertEqual(ev([order("B", "Complete", ["Paid"])], [ship("B", "in_transit")]), {})

    def test_beleg_ohne_sendung_mittel_nur_alt(self):
        alt = "[2026-01-14 10:00 ev:abcd1234] BELEG INVOICE: Rechnung X (Mail 1)"
        neu = "[2026-10-20 10:00 ev:abcd1234] BELEG INVOICE: Rechnung X (Mail 1)"
        self.assertEqual(ev([order("A", "Draft", notes=alt)])["A"]["sicherheit"], "mittel")
        self.assertEqual(ev([order("A", "Draft", notes=neu)])["A"]["art"], "Hinweis")
        self.assertEqual(ev([order("A", "Draft", notes=alt)], [ship("A", "pending")])["A"]["art"], "Hinweis")   # offene Sendung: kein Beleg-Schluss

    def test_complete_nur_voll_belegt(self):
        r = ev([order("A", "In Transit", ["Paid", "Paid"])], [ship("A", "delivered")])["A"]
        self.assertEqual((r["ziel"], r["sicherheit"], r["auto"]), ("Complete", "hoch", True))
        r = ev([order("A", "In Transit", ["Paid"])], [ship("A", "delivered", qty=50)])["A"]
        self.assertEqual((r["ziel"], r["sicherheit"], r["auto"]), ("Complete", "mittel", False))   # Menge fehlt
        r = ev([order("A", "In Transit", ["Paid", "Unpaid"])], [ship("A", "delivered")])["A"]
        self.assertEqual((r["ziel"], r["regel"], r["sicherheit"], r["auto"]), ("Complete", "COMPLETE_RATEN_OFFEN", "niedrig", False))
        r = ev([order("A", "In Transit", ["Paid"])], [ship("A", "delivered"), ship("A", "pending")])
        self.assertNotIn("A", r)   # Sendung offen

    def test_hoch_und_hoeherer_vorschlag(self):
        # Draft mit Paid-Rate und delivered Sendung, Raten offen: sicheres In Transit bleibt, Complete nur als eigener niedriger Vorschlag
        rows = sr.evaluate([order("A", "Draft", ["Paid", "Unpaid"])], [ship("A", "delivered")], today=TODAY)
        self.assertEqual([(r["ziel"], r["sicherheit"]) for r in rows], [("In Transit", "hoch"), ("Complete", "niedrig")])
        self.assertEqual(len(sr.auto_candidates(rows)), 1)

    def test_ereignis_nicht_auto(self):
        rows = sr.evaluate([order("A", "Draft")], [], today=TODAY, event_status={"A": {"to": "In Production", "why": "PRODUCTION_STARTED (m1)"}})
        self.assertEqual((rows[0]["ziel"], rows[0]["sicherheit"], rows[0]["auto"]), ("In Production", "hoch", False))   # schreibt events.py

    def test_complete_mit_offenen_raten_hinweis(self):
        r = ev([order("A", "Complete", ["Paid", "Unpaid"])])["A"]
        self.assertEqual((r["art"], r["ziel"]), ("Hinweis", "Complete"))

    def test_nicht_belegbar_und_platzhalter_und_test(self):
        o = [order("A", "Draft"), order("B", "Draft", cost=0), order("C", "Draft", ["Paid"], title="ZZ-TEST-1")]
        r = ev(o)
        self.assertEqual(r["A"]["regel"], "HINWEIS_NICHT_BELEGBAR")
        self.assertNotIn("B", r); self.assertNotIn("C", r)

    def test_rechnung_als_basis(self):
        n = "Quelle: PO X (Mail vom 2026-03-04). Phase 2: Menge = bisher gelieferte Menge laut Rechnungen AK/1."
        r = ev([order("A", "Draft", notes=n)])["A"]
        self.assertEqual((r["regel"], r["sicherheit"], r["auto"]), ("RECHNUNG_ALS_BASIS", "mittel", False))

    def test_csv_und_md(self):
        rows = sr.evaluate([order("A", "Draft", ["Paid"]), order("B", "Complete", ["Unpaid"])], [], today=TODAY)
        with tempfile.TemporaryDirectory() as d:
            sr.write_csv(rows, Path(d) / "x.csv")
            back = sa.read_csv(Path(d) / "x.csv")
        self.assertEqual(back[0]["Freigabe"], ""); self.assertEqual(list(back[0].keys()), sr.CSV_COLS)
        md = sr.render_md(rows, 0, TODAY)
        self.assertIn("Hoch", md); self.assertIn("HINWEIS_COMPLETE_RATEN_OFFEN", md)


class Apply(unittest.TestCase):
    def test_nur_freigegebene_zeilen(self):
        rows = [{"Order-ID": "A", "Freigabe": "ja", "Art": "Aenderung"}, {"Order-ID": "B", "Freigabe": "nein", "Art": "Aenderung"},
                {"Order-ID": "C", "Freigabe": "", "Art": "Aenderung"}, {"Order-ID": "D", "Freigabe": "ja", "Art": "Hinweis"}]
        self.assertEqual([r["Order-ID"] for r in sa.approved(rows)], ["A"])

    def test_plan_prueft_ist_status_und_richtung(self):
        orders = [order("A", "Draft"), order("B", "Complete"), order("C", "In Transit"), order("D", "Approved")]
        rows = [{"Order-ID": "A", "Aktuell": "Draft", "Ziel": "Approved"}, {"Order-ID": "B", "Aktuell": "Complete", "Ziel": "Complete"},
                {"Order-ID": "C", "Aktuell": "In Transit", "Ziel": "Approved"}, {"Order-ID": "D", "Aktuell": "Draft", "Ziel": "In Transit"},
                {"Order-ID": "X", "Aktuell": "Draft", "Ziel": "Approved"}]
        todo, skip = sa.plan(rows, orders, ST)
        self.assertEqual([t["id"] for t in todo], ["A"]); self.assertEqual(len(skip), 4)

    def test_limit(self):
        orders = [order("A%d" % i, "Draft") for i in range(5)]
        rows = [{"Order-ID": o["id"], "Aktuell": "Draft", "Ziel": "Approved"} for o in orders]
        todo, skip = sa.plan(rows, orders, ST, limit=2)
        self.assertEqual(len(todo), 2); self.assertEqual(len(skip), 3)

    def test_trockenlauf_schreibt_nichts(self):
        calls = []
        L, res = sa.execute([{"id": "A", "title": "PO-A", "from": "Draft", "to": ST["Approved"]}], False, runner=lambda js: calls.append(js))
        self.assertEqual(calls, []); self.assertEqual(res["gesetzt"], 0)

    def test_apply_backup_vor_schreiben_und_zuruecklesen(self):
        todo = [{"id": "A", "title": "PO-A", "from": "Draft", "to": ST["Approved"]}]
        order_ = []

        def runner(js):
            if "__updOrder" in js:
                order_.append("write"); return [{"title": "PO-A", "statusOk": True, "dataUnchanged": True}]
            order_.append("read"); return {"A": {"id": "A"}}
        L, res = sa.execute(todo, True, runner=runner, backup_fn=lambda b, t: order_.append("backup") or "p")
        self.assertEqual(order_, ["read", "backup", "write"]); self.assertEqual((res["gesetzt"], res["fehler"]), (1, 0))

    def test_abweichung_zaehlt_als_fehler(self):
        todo = [{"id": "A", "title": "PO-A", "from": "Draft", "to": ST["Approved"]}]
        ok, errs = sa.verify(todo, [{"title": "PO-A", "statusOk": True, "dataUnchanged": False, "ABBRUCH": "x"}])
        self.assertEqual((ok, len(errs)), (0, 1))
        ok, errs = sa.verify(todo, [])
        self.assertEqual((ok, len(errs)), (0, 1))

    def test_auto_standard_aus_und_limit(self):
        orders = [order("O%d" % i, "Draft", ["Paid"]) for i in range(12)]
        calls = []
        L, res = sa.auto(orders, [], ST, True, env={}, runner=lambda js: calls.append(js))
        self.assertEqual((calls, res["gesetzt"], res["vorschlaege"], res["auto"]), ([], 0, 12, False))
        L, res = sa.auto(orders, [], ST, False, env={"STATUS_AUTO": "1"}, runner=lambda js: calls.append(js))   # Trockenlauf: auch mit Schalter nichts
        self.assertEqual(calls, [])

        def runner(js):
            if "__updOrder" in js:
                plan = json.loads(js.split("const PLAN = ")[1].split(";\n")[0])
                self.assertEqual(len(plan), 10)
                return [{"title": p["title"], "statusOk": True, "dataUnchanged": True} for p in plan]
            return {}
        L, res = sa.auto(orders, [], ST, True, env={"STATUS_AUTO": "1"}, runner=runner, backup_fn=lambda b, t: "p")
        self.assertEqual((res["gesetzt"], res["fehler"]), (10, 0))

    def test_auto_nur_hoch(self):
        orders = [order("A", "Approved")]
        calls = []
        L, res = sa.auto(orders, [ship("A", "pending", "1")], ST, True, env={"STATUS_AUTO": "1"}, runner=lambda js: calls.append(js))   # nur mittel
        self.assertEqual((calls, res["gesetzt"], res["vorschlaege"]), ([], 0, 1))


class Bericht(unittest.TestCase):
    def test_zeile(self):
        self.assertIn("Status: Vorschlaege 5, gesetzt 2", _bericht({"status": {"vorschlaege": 5, "gesetzt": 2, "fehler": 0, "auto": True}}))


def _bericht(extra):
    facts = {"zahlen": {}, "warnungen": []}
    facts.update(extra)
    return tb.build(facts, 0, "apply", now=dt.datetime(2026, 10, 26, 8, 0), verlauf={})


if __name__ == "__main__":
    unittest.main()
