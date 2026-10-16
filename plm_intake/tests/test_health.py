import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import audit, health, ledger  # noqa: E402

NOW = dt.datetime(2026, 10, 16, 13, 30)
REPORT = """# Alltagslauf x

Neu: 4 Dokument-Dateien, 7 Ereignis-Dateien

## Neue Bestellungen (CREATE)
- a.json -> PO-A (10 Stk, 5)
- b.json -> PO-B (10 Stk, 5)

## Sendungen (Bereich Shipments)
- neu: Sendung X (sea, pending, 2 Pos.)
- Mensch: foo: bar

## Mensch entscheidet (12)
- x
"""


class Health(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(); self.intake = Path(self.d.name)
        self.p = mock.patch("plm_intake.health.notify"); self.notify = self.p.start()

    def tearDown(self):
        self.p.stop(); self.d.cleanup()

    def test_preflight_ok(self):
        ok, msgs = health.preflight(self.intake, rest=lambda: (True, "REST ok"), browser=lambda: (True, "Browser eingeloggt"), now=NOW)
        self.assertTrue(ok); self.notify.assert_not_called()

    def test_preflight_nicht_eingeloggt_warnt_und_stoppt(self):
        ok, msgs = health.preflight(self.intake, rest=lambda: (True, "REST ok"), browser=lambda: (False, "PLM-Browser NICHT eingeloggt"), now=NOW)
        self.assertFalse(ok); self.notify.assert_called()
        self.assertIn("NICHT eingeloggt", (self.intake / "alerts.log").read_text())
        self.assertEqual(health.load_status(self.intake)["state"], "ALARM")

    def test_browser_exit3_ist_login_problem_andere_codes_sind_browserfehler(self):
        self.assertIn("NICHT eingeloggt", health.check_browser(lambda: (3, ""))[1])
        ok, m = health.check_browser(lambda: (1, "boom")); self.assertFalse(ok); self.assertIn("Exit 1", m)
        self.assertTrue(health.check_browser(lambda: (0, "{}"))[0])

    def test_rest_fehler(self):
        self.assertFalse(health.check_rest(lambda *a, **k: (401, {}))[0])
        def boom(*a, **k): raise OSError("net")
        self.assertFalse(health.check_rest(boom)[0])

    def test_summarize_zaehlt(self):
        st, txt = health.summarize(REPORT, 0)
        self.assertEqual(st, "OK"); self.assertIn("4 neue Dokumente", txt); self.assertIn("neue POs 2", txt); self.assertIn("Sendungen 1", txt); self.assertIn("entscheidet: 12", txt)

    def test_abbruch_oder_exit_ist_alarm(self):
        self.assertEqual(health.summarize(REPORT + "\nABBRUCH: unsicher", 0)[0], "ALARM")
        self.assertEqual(health.summarize(REPORT, 1)[0], "ALARM")

    def test_finish_schreibt_status_und_warnt_nur_bei_problem(self):
        (self.intake / "auto_report.md").write_text(REPORT)
        self.assertEqual(health.finish(self.intake, 0, "dry", NOW)[0], "OK"); self.notify.assert_not_called()   # ruhiger Mittags-Lauf: keine Mitteilung
        self.assertEqual(health.finish(self.intake, 1, "apply", NOW)[0], "ALARM"); self.notify.assert_called()
        s = (self.intake / "STATUS.md").read_text(); self.assertIn("ALARM", s); self.assertIn("2026-10-16 13:30", s)
        self.assertEqual(health.load_status(self.intake)["last_ok"], "2026-10-16T13:30:00")

    def test_veraltet(self):
        health.write_status(self.intake, "OK", "x", now=NOW - dt.timedelta(hours=30))
        self.assertGreater(health.stale_hours(health.load_status(self.intake), NOW), 26)
        health.preflight(self.intake, rest=lambda: (True, "REST ok"), browser=lambda: (True, "ok"), now=NOW)
        self.assertIn("Lange kein erfolgreicher Lauf", (self.intake / "alerts.log").read_text())


DOC = {"items": [{"sku": "A", "variants": [{"price": 2, "sizes": {"S": 5, "M": 5}}]}, {"sku": "B", "variants": [{"price": 1, "quantity": 10}]}]}


def live(pcs_a=10, pcs_b=10, cost=30.0, title="PO-T"):
    return {"id": "o1", "orderNumber": 7, "title": title, "totalCost": cost, "poNumber": "T-1", "manufacturer": {"id": "V"},
            "items": [{"variants": [{"amounts": [{"quantity": pcs_a}]}]}, {"variants": [{"amounts": [{"quantity": pcs_b}]}]}]}


class InboxAlter(unittest.TestCase):
    def test_schwellen(self):
        di = dt.datetime
        self.assertFalse(health.inbox_stale(10, di(2026, 10, 14, 13)))     # Mittwoch, frisch
        self.assertTrue(health.inbox_stale(31, di(2026, 10, 14, 13)))      # Mittwoch, 31 h
        self.assertFalse(health.inbox_stale(60, di(2026, 10, 12, 8)))      # Montag frueh nach dem Wochenende
        self.assertTrue(health.inbox_stale(70, di(2026, 10, 12, 8)))
        self.assertFalse(health.inbox_stale(100, di(2026, 10, 17, 13)))    # Samstag nie
        self.assertFalse(health.inbox_stale(None, di(2026, 10, 14, 13)))   # unbekannt: keine Warnung

    def test_preflight_warnt_bei_veralteter_inbox_aber_bricht_nicht_ab(self):
        import os
        with tempfile.TemporaryDirectory() as d, mock.patch("plm_intake.health.notify") as n:
            inbox = Path(d) / "in"; inbox.mkdir(); f = inbox / "a.json"; f.write_text("{}")
            old = (NOW - dt.timedelta(hours=40)).timestamp(); os.utime(f, (old, old))
            ok, msgs = health.preflight(Path(d) / "n", rest=lambda: (True, "REST ok"), browser=lambda: (True, "ok"), now=NOW, inbox=inbox)
            self.assertTrue(ok); n.assert_called(); self.assertTrue(any("Inbox" in m for m in msgs))


class Audit(unittest.TestCase):
    def test_totals_und_vergleich(self):
        self.assertEqual(audit.source_totals(DOC), (20, 30.0, [10, 10]))
        self.assertEqual(audit.compare("f", DOC, live()), [])
        self.assertTrue(any("Stueck" in b for b in audit.compare("f", DOC, live(pcs_a=9))))
        self.assertTrue(any("Wert" in b for b in audit.compare("f", DOC, live(cost=99))))

    def test_run_findet_abweichung_marker_bank_und_dublette(self):
        with tempfile.TemporaryDirectory() as d:
            inbox, intake = Path(d) / "i", Path(d) / "n"; inbox.mkdir(); intake.mkdir()
            (inbox / "m1_1.json").write_text(json.dumps(DOC))
            led = {}; ledger.mark(led, inbox / "m1_1.json", "applied", "PO-T"); ledger.save(intake / "ledger.json", led)
            good = live()
            bad, info = audit.run(inbox, intake, [good], 5, 1)
            self.assertEqual(bad, []); self.assertIn("stimmt", info[0])
            bad, _ = audit.run(inbox, intake, [live(pcs_a=8)], 5, 1); self.assertTrue(bad)
            leak = dict(live(), notes="IBAN DE89 3704 0044 0532 0130 00"); self.assertTrue(any("BANKDATEN" in b for b in audit.run(inbox, intake, [leak], 5, 1)[0]))
            dup = dict(live(), id="o2", orderNumber=8); self.assertTrue(any("DUBLETTE" in b for b in audit.run(inbox, intake, [good, dup], 5, 1)[0]))

    def test_keine_falschen_bankdaten_bei_containernummern(self):
        self.assertEqual(audit.bank_findings([{"title": "x", "notes": "Container MSKU1234567, BL 065-4958 9923, AK/623/26"}]), [])


if __name__ == "__main__":
    unittest.main()
