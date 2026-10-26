import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import payments_plan as pp, tagesbericht as tb  # noqa: E402

PH = {"id": "P0", "name": "Gesamtbetrag (Platzhalter)", "status": "Unpaid", "amount": 1000.0, "dueDate": "1792368000000", "terms": ""}


def order(oid="O1", title="PO-A-1", notes="", total=1000.0, pays=None, vendor=("V1", "Alpha"), etd=None, exf=None):
    return {"id": oid, "title": title, "notes": notes, "totalCost": total, "currency": "USD", "etdEstimatedDate": etd, "exFactoryExpectedDate": exf,
            "manufacturer": {"id": vendor[0], "name": vendor[1]}, "status": {"status": "Draft"}, "payments": [PH] if pays is None else pays}


T4 = "PO-Datum 2026-03-18, Incoterm FOB. Zahlungsbedingungen: ['15% deposit before production', '10% by shipment', '35% 40 days after shipment', '40% 80 days after shipping']. Offen: Zahlungsbedingungen unbekannt."


class Parse(unittest.TestCase):
    def test_test_orders_und_platzhalter(self):
        for t in ("ZZ-X", "PO-A-T1", "Mein TEST"):
            self.assertTrue(pp.is_test(t))
        self.assertFalse(pp.is_test("PO-ALPHA-1"))
        self.assertTrue(pp.is_placeholder(order()))
        self.assertTrue(pp.is_placeholder(order(pays=[dict(PH, name="Gesamtbetrag (Platzhalter, Zahlungsbedingungen TBC)")])))
        self.assertFalse(pp.is_placeholder(order(pays=[dict(PH, name="30% Deposit"), dict(PH, name="70% Balance")])))
        self.assertFalse(pp.is_placeholder(order(pays=[])))

    def test_doc_terms_formen(self):
        self.assertEqual(pp.doc_terms(T4)[0], "15% deposit before production")
        self.assertEqual(len(pp.doc_terms(T4)), 4)
        sem = "x. Zahlungsbedingungen: 15% deposit before production; 10% by shipment; 35% 40 days after shipment; 40% 80 days after shipping (keine Betraege/Termine in der Quelle). Rest"
        self.assertEqual(len(pp.doc_terms(sem)), 4)
        self.assertEqual(pp.doc_terms("Zahlungsbedingungen: ['T/T 30% deposit once PI confirmed, balance against copy B/L']. Offen"), ["T/T 30% deposit once PI confirmed", "balance against copy B/L"])
        self.assertIsNone(pp.doc_terms("keine Angabe"))

    def test_plan_prozente(self):
        raten, err = pp.parse_plan(pp.doc_terms(T4))
        self.assertIsNone(err); self.assertEqual([r["pct"] for r in raten], [15, 10, 35, 40])
        self.assertEqual([r["anchor"] for r in raten], ["po", "ship", "ship", "ship"]); self.assertEqual([r["days"] for r in raten], [0, 0, 40, 80])
        raten, err = pp.parse_plan(["T/T 30% deposit once PI confirmed", "balance against copy B/L"])
        self.assertEqual([r["pct"] for r in raten], [30, 70])
        self.assertIsNotNone(pp.parse_plan(["30% deposit", "40% balance"])[1])   # 70 statt 100
        self.assertIsNotNone(pp.parse_plan(["TBA"])[1]); self.assertIsNotNone(pp.parse_plan(["TBC laut PI"])[1])
        self.assertIsNotNone(pp.parse_plan(["100% deposit", "balance"])[1])      # kein Rest
        self.assertIsNotNone(pp.parse_plan(["balance a", "50% b", "balance c"])[1])

    def test_open_account(self):
        n = "[2026-10-14 20:08 ev:d65d178f] BELEG INVOICE: INVOICE X | 10852 Stk | 69671.6 EUR | Zahlungen: MAL MUKABİLİ 69671.6 Unpaid: Text (Mail 1)\n[2026-10-20 17:17 ev:8e70253e] BELEG INVOICE: INVOICE ? | 1 Stk | 12 EUR | Zahlungen: Mal Mukabili 12 Unpaid: Ödeme (Mail 2)"
        self.assertEqual(pp.open_account_term(n), "Mal Mukabili (Zahlung gegen Ware)")
        self.assertIsNone(pp.open_account_term(n + "\n[2026-10-21 01:00 ev:aaaaaaaa] BELEG INVOICE: X | Zahlungen: 20% Deposit 5 Unpaid: y (Mail 3)"))
        self.assertIsNone(pp.open_account_term("nichts"))


class Plan(unittest.TestCase):
    def test_plan_aus_bedingungen_summe_und_faelligkeit(self):
        o = order(notes=T4, total=1000.01, etd="2026-09-01T00:00:00.000Z")
        a = pp.plan([o], {"V1": "15% deposit before production 10% by shipment 35% 40 days after shipment 40% 80 days after shipping"})["actions"][0]
        self.assertEqual(a["kind"], "plan")
        rows = a["rows"]
        self.assertEqual([r["name"] for r in rows], ["15% deposit before production", "10% by shipment", "35% 40 days after shipment", "40% 80 days after shipping"])
        self.assertAlmostEqual(sum(r["amount"] for r in rows), 1000.01, places=2)   # letzte Rate = Rest
        self.assertEqual(rows[0]["amount"], 150.0)
        self.assertEqual({r["status"] for r in rows}, {"Unpaid"}); self.assertEqual(rows[0]["terms"], "15% deposit before production")
        d = lambda r: dt.datetime.fromtimestamp(r["dueDate"] / 1000, dt.timezone.utc).date().isoformat()
        self.assertEqual([d(rows[0]), d(rows[1]), d(rows[2]), d(rows[3])], ["2026-03-18", "2026-09-01", "2026-10-11", "2026-11-20"])

    def test_keine_faelligkeit_erfunden(self):
        rows = pp.plan([order(notes=T4)])["actions"][0]["rows"]
        self.assertEqual([r["dueDate"] is None for r in rows], [False, True, True, True])   # ohne ETD/ex-factory nur das Deposit mit PO-Datum
        rows = pp.plan([order(notes=T4.replace("PO-Datum 2026-03-18, ", ""))])["actions"][0]["rows"]
        self.assertTrue(all(r["dueDate"] is None for r in rows))

    def test_ohne_bedingungen_platzhalter_entfernt_klaerfall_je_lieferant(self):
        os_ = [order("O1", "PO-A-1", "Offen: Zahlungsbedingungen unbekannt."), order("O2", "PO-A-2", "Offen: Zahlungsbedingungen unbekannt.")]
        r = pp.plan(os_)
        self.assertEqual([a["kind"] for a in r["actions"]], ["placeholder", "placeholder"])
        self.assertEqual(len(r["klaer"]), 1); self.assertIn("2 Orders", r["klaer"][0]["values"]["Was"]); self.assertEqual(r["klaer"][0]["category"], "Alpha")
        self.assertEqual(r["klaer"][0]["values"]["Art"], "Zahlung"); self.assertRegex(r["klaer"][0]["values"]["Quelle"], r"ev:[0-9a-f]{8}$")

    def test_nur_lieferantenrahmen_ist_klaerfall_keine_automatik(self):
        r = pp.plan([order(notes="Offen: Zahlungsbedingungen unbekannt.")], {"V1": "30% deposit 70% balance"})
        self.assertEqual(r["actions"][0]["kind"], "placeholder"); self.assertEqual(len(r["klaer"]), 1); self.assertIn("Lieferanten-Rahmen", r["klaer"][0]["values"]["Was"])

    def test_widerspruch_order_vs_lieferant(self):
        r = pp.plan([order(notes=T4)], {"V1": "35% Deposit 65% balance against copy of B/L"})
        self.assertEqual(r["actions"][0]["kind"], "placeholder"); self.assertIn("widerspruechlich", r["klaer"][0]["values"]["Was"])
        self.assertNotIn("rows", r["actions"][0])

    def test_gleiche_prozente_kein_widerspruch(self):
        r = pp.plan([order(notes=T4)], {"V1": "15% deposit before production, 10% by shipment, 35% after shipment, 40% 80 days"})
        self.assertEqual(r["actions"][0]["kind"], "plan"); self.assertEqual(r["klaer"], [])

    def test_open_account_plan_und_tba(self):
        n = "Zahlungsbedingungen: ['TBA']. x\n[2026-10-14 20:08 ev:d65d178f] BELEG INVOICE: INVOICE X | 1 Stk | 1000 EUR | Zahlungen: MAL MUKABILI 1000 Unpaid: T (Mail 1)"
        a = pp.plan([order(notes=n, etd="2026-09-16T00:00:00.000Z")])["actions"][0]
        self.assertEqual((a["kind"], len(a["rows"]), a["rows"][0]["amount"]), ("plan", 1, 1000.0)); self.assertTrue(a["rows"][0]["dueDate"])
        r = pp.plan([order(notes="Zahlungsbedingungen: ['TBA']. x")])
        self.assertEqual(r["actions"][0]["kind"], "placeholder"); self.assertEqual(len(r["klaer"]), 1)

    def test_echte_plaene_bleiben_test_orders_ignoriert(self):
        real = [{"id": "p1", "name": "30% Deposit", "status": "Paid", "amount": 300.0, "dueDate": "1", "terms": ""}, {"id": "p2", "name": "70%", "status": "Unpaid", "amount": 700.0, "dueDate": "2", "terms": ""}]
        r = pp.plan([order(pays=real), order("O2", "ZZ-TEST-1"), order("O3", "PO-X-T1")])
        self.assertEqual(r["actions"], []); self.assertEqual(r["klaer"], [])

    def test_echter_plan_summe_abweichung_ist_klaerfall_ohne_aenderung(self):
        real = [{"id": "p1", "name": "a", "status": "Unpaid", "amount": 300.0, "dueDate": "1", "terms": ""}, {"id": "p2", "name": "b", "status": "Unpaid", "amount": 600.0, "dueDate": "2", "terms": ""}]
        r = pp.plan([order(pays=real)])
        self.assertEqual(r["actions"], []); self.assertEqual(len(r["klaer"]), 1); self.assertIn("Summe", r["klaer"][0]["values"]["Was"])

    def test_eigener_plan_ohne_faelligkeiten_ist_kein_klaerfall(self):
        pays = [{"id": "p%d" % i, "name": "x", "status": "Unpaid", "amount": 250.0, "dueDate": None, "terms": ""} for i in range(4)]
        self.assertEqual(pp.plan([order(pays=pays)])["klaer"], [])

    def test_limit_pro_lauf(self):
        os_ = [order("O%d" % i, "PO-A-%02d" % i, "Offen: unbekannt.") for i in range(14)]
        r = pp.plan(os_, max_orders=10)
        self.assertEqual((len(r["actions"]), r["limit_offen"], r["alle"]), (10, 4, 14))


class Paid(unittest.TestCase):
    REAL = [{"id": "p1", "name": "20% Deposit", "status": "Unpaid", "amount": 3406.0, "dueDate": "1", "terms": ""},
            {"id": "p2", "name": "15% bei Versand", "status": "Unpaid", "amount": 2125.5, "dueDate": "2", "terms": ""},
            {"id": "p3", "name": "65% Rest", "status": "Unpaid", "amount": 11500.0, "dueDate": "3", "terms": ""}]

    def beleg(self, extra=""):
        return "[2026-10-21 11:11 ev:cc941089] BELEG INVOICE: INVOICE LIEFERANT_AA2674 | 2704 Stk | 17031.5 USD | Zahlungen: 20% Anzahlung 3406 Paid, 15% bei Versand 2125.5 Paid, 65% Rest 11500 Unpaid: Commercial Invoice (Mail 1)" + extra

    def test_paid_bei_genau_einem_betragstreffer(self):
        r = pp.plan([order(notes=self.beleg(), pays=self.REAL, total=17031.5)])
        a = r["actions"][0]
        self.assertEqual(a["kind"], "paid"); self.assertEqual([i for i, _, _ in a["paid"]], [0, 1])
        self.assertEqual(pp.counts([a])["paid"], 2)

    def test_kein_paid_bei_zwei_gleichen_betraegen_oder_ohne_treffer(self):
        two = [dict(self.REAL[0]), dict(self.REAL[0], id="px", name="zweite gleiche"), self.REAL[2]]
        self.assertEqual(pp.plan([order(notes=self.beleg(), pays=two, total=18000.0)])["actions"], [])
        self.assertEqual(pp.plan([order(notes=self.beleg(), pays=[dict(self.REAL[0], amount=3407.0), self.REAL[2]], total=14907.0)])["actions"], [])

    def test_zahlung_ohne_betrag_oder_mahnung_bleibt_notiz(self):
        for line in ("[2026-10-14 10:52 ev:3c5da8da] PAYMENT: Balance payment was arranged last Monday. Bank slip will be forwarded once received. (Mail 1)",
                     "[2026-10-12 22:02 ev:7004142a] PAYMENT: Vendor is following up on the overdue outstanding balance of USD 3,406.00 against B/L. (Mail 2)",
                     "[2026-10-12 22:02 ev:0e9f9c30] PAYMENT: The payment has been processed today and the bank slip is expected by Wednesday. (Mail 3)"):
            self.assertEqual(pp.plan([order(notes=line, pays=self.REAL, total=17031.5)])["actions"], [], line)

    def test_zahlungsmeldung_mit_einem_betrag(self):
        line = "[2026-10-20 09:31 ev:a38974f7] PAYMENT: 35% payment of USD 2,125.50 made for order X (Mail 1)"
        a = pp.plan([order(notes=line, pays=self.REAL, total=17031.5)])["actions"][0]
        self.assertEqual([(i, w) for i, w, _ in a["paid"]], [(1, "Zahlungsmeldung")])

    def test_paid_bleibt_bei_bereits_paid_unberuehrt(self):
        done = [dict(self.REAL[0], status="Paid"), dict(self.REAL[1], status="Paid"), self.REAL[2]]
        self.assertEqual(pp.plan([order(notes=self.beleg(), pays=done, total=17031.5)])["actions"], [])


class Schreiben(unittest.TestCase):
    def test_write_payload_fuer_plan_leer_und_paid(self):
        got = {}
        def runner(js):
            got["js"] = js; return []
        acts = [{"id": "O1", "title": "A", "kind": "plan", "total": 100.0, "before": [PH], "rows": [{"name": "50%", "status": "Unpaid", "amount": 50.0, "terms": "t", "dueDate": None}, {"name": "50% b", "status": "Unpaid", "amount": 50.0, "terms": "t", "dueDate": 5}]},
                {"id": "O2", "title": "B", "kind": "placeholder", "total": 100.0, "before": [PH]},
                {"id": "O3", "title": "C", "kind": "paid", "total": 100.0, "paid": [(0, "x", 1)], "before": [{"id": "z", "name": "n", "status": "Unpaid", "amount": 100.0, "dueDate": "99", "terms": "t"}]}]
        pp.write(acts, False, runner)
        js = got["js"]
        self.assertIn("const DRY = false", js)
        plan = json.loads(js.split("const PLAN = ")[1].split(";\n")[0])
        self.assertNotIn("dueDate", plan[0]["payments"][0]); self.assertEqual(plan[0]["payments"][1]["dueDate"], 5)
        self.assertEqual(plan[1]["payments"], [])
        self.assertEqual(plan[2]["payments"][0]["status"], "Paid"); self.assertEqual(plan[2]["payments"][0]["dueDate"], 99)
        self.assertEqual(plan[0]["before"][0]["name"], "Gesamtbetrag (Platzhalter)")

    def test_verify_meldet_fehler_und_nicht_ausgefuehrte(self):
        acts = [{"title": "A"}, {"title": "B"}, {"title": "C"}, {"title": "D"}]
        res = [{"title": "A", "dataUnchanged": True, "paymentsOk": True, "sumOk": True}, {"title": "B", "error": "x"},
               {"title": "C", "dataUnchanged": False, "paymentsOk": True, "sumOk": True}]
        ok, errs = pp.verify(acts, res)
        self.assertEqual(ok, 1); self.assertEqual(len(errs), 3)

    def test_run_trockenlauf_schreibt_nichts_apply_mit_backup(self):
        orders = [order(notes=T4)]
        calls = []
        def runner(js):
            calls.append(js)
            if "getOrderById" in js:
                return {"orders": orders, "vendors": {}, "err": []}
            if "const PLAN" in js:
                return [{"title": "PO-A-1", "dataUnchanged": True, "paymentsOk": True, "sumOk": True}]
            return {"created": 0, "errors": []}
        L, res = pp.run([{"id": "O1", "title": "PO-A-1"}], False, runner=runner)
        self.assertEqual(len(calls), 1); self.assertEqual(res["plaene"], 0)
        with tempfile.TemporaryDirectory() as d:
            saved = []
            def bk(actions, by_id):
                p = Path(d) / "b.json"; p.write_text(json.dumps([a["id"] for a in actions])); saved.append(p); return p
            L, res = pp.run([{"id": "O1", "title": "PO-A-1"}], True, runner=runner, backup_fn=bk)
            self.assertEqual(res["plaene"], 1); self.assertEqual(res["fehler"], 0); self.assertTrue(saved)
            self.assertTrue(any("const PLAN" in c for c in calls))

    def test_run_abbruch_bei_fehler_traegt_keine_klaerfaelle_ein(self):
        orders = [order(notes="Offen: unbekannt.")]
        calls = []
        def runner(js):
            calls.append(js)
            if "getOrderById" in js:
                return {"orders": orders, "vendors": {}, "err": []}
            return [{"title": "PO-A-1", "error": "boom"}]
        L, res = pp.run([{"id": "O1", "title": "PO-A-1"}], True, runner=runner, backup_fn=lambda a, b: "bk")
        self.assertEqual(res["fehler"], 1); self.assertEqual(res["platzhalter"], 0)
        self.assertFalse(any("createCustomRow" in c for c in calls))

    def test_backup_vollstaendig_mit_ids(self):
        with tempfile.TemporaryDirectory() as d:
            old = pp.BACKUP_DIR; pp.BACKUP_DIR = Path(d)
            try:
                p = pp.backup([{"id": "O1", "title": "A", "kind": "placeholder"}], {"O1": order()}, dt.datetime(2026, 10, 26, 12, 0, 0))
            finally:
                pp.BACKUP_DIR = old
            data = json.loads(p.read_text())
            self.assertEqual(p.name, "payments_vor_2026-10-26_120000.json"); self.assertEqual(data[0]["payments_vorher"][0]["id"], "P0")


class Bericht(unittest.TestCase):
    def test_tagesbericht_zeile(self):
        facts = {"zahlen": {}, "zahlungen": {"platzhalter": 3, "plaene": 2, "klaerfaelle": 4, "paid": 1, "fehler": 0}}
        txt = tb.build(facts, 0, "apply", now=dt.datetime(2026, 10, 27, 8, 0))
        self.assertIn("Zahlungen: Platzhalter entfernt 3, Plaene aufgebaut 2, Klaerfaelle 4, Paid gesetzt 1, Fehler 0", txt)
        facts["zahlungen"]["fehler"] = 1
        self.assertIn("WARNUNG", tb.build(facts, 0, "apply", now=dt.datetime(2026, 10, 27, 8, 0)).split("Zahlungen:")[1].split("\n")[0])


if __name__ == "__main__":
    unittest.main()
