import datetime as dt
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import tagesbericht as tb  # noqa: E402

DI = dt.datetime(2026, 10, 20, 8, 30)   # Dienstag
MI = dt.datetime(2026, 10, 21, 8, 30)   # Mittwoch
FR = dt.datetime(2026, 10, 23, 13, 40)  # Freitag


def facts(n_pool=15, n_rows=7):
    return {"zahlen": {"orders": 1, "notes": 12, "ship_new": 1, "ship_upd": 2, "techpacks": 3},
            "klaer_rows": [{"marker": "m%d" % i, "category": "Lieferant%d" % i, "values": {"Warum offen": "keine Order gefunden %d" % i}} for i in range(n_rows)],
            "klaer_offen": 61, "warnungen": ["BLOCK empty_order (x.json): leer", "PO-1: UNSTIMMIG: Positionen 10 != 12"],
            "aliase": [{"key": "26WJD-107", "order": "PO-LIEFERANT_AA-107", "quelle": "Mail"}],
            "stichprobe_pool": [{"order": "PO-%d" % i, "betreff": "Betreff %d" % i, "text": "Notiz %d" % i} for i in range(n_pool)], "dauer_s": 420}


class Warnungen(unittest.TestCase):
    def test_schluessel(self):
        self.assertEqual(tb.warn_key("BLOCK empty_order (x.json): leer"), "BLOCK empty_order (x.json)")
        self.assertEqual(tb.warn_key("Bestellungen mit Summe 0 im PLM (3): a, b"), "Bestellungen mit Summe 0 im PLM")
        self.assertEqual(tb.warn_key("UNSTIMMIG/Mensch: Sendung S1: Menge 3 != 4"), "UNSTIMMIG/Mensch: Sendung S1")

    def test_neu_bekannt_und_entfernen(self):
        w = ["BLOCK empty_order (a.json): x", "BLOCK price_missing (b.json): y", "NEU (c): z"]
        verlauf = {"tage": {"2026-10-19": 5}, "gesehen": ["m"], "warnungen": {"BLOCK empty_order (a.json)": "2026-10-10", "BLOCK price_missing (b.json)": "2026-10-20", "ALT (weg): q": "2026-10-01"}}
        t = tb.build({"zahlen": {}, "warnungen": w}, 0, "apply", now=FR, verlauf=verlauf)
        self.assertIn("4. Warnungen: 1 neu | 2 bekannte Warnungen seit frueheren Laeufen (aelteste besteht seit 13 Tagen)", t)
        self.assertIn("- NEU (c): z", t); self.assertNotIn("a.json", t)
        _, _, _, stand = tb.warnungen_split(w, verlauf, FR)
        self.assertNotIn("ALT (weg): q", stand); self.assertEqual(stand["NEU (c)"], "2026-10-23"); self.assertEqual(stand["BLOCK empty_order (a.json)"], "2026-10-10")

    def test_max_acht_neue_und_nur_bekannte(self):
        w = ["W%d (f): x" % i for i in range(11)]
        t = tb.build({"zahlen": {}, "warnungen": w}, 0, "apply", now=FR, verlauf={})
        self.assertIn("11 neu", t); self.assertIn("und 3 weitere neue", t)
        stand = tb.warnungen_split(w, {}, FR)[3]
        t2 = tb.build({"zahlen": {}, "warnungen": w}, 0, "apply", now=FR + dt.timedelta(days=1), verlauf={"warnungen": stand})
        self.assertIn("4. Warnungen: 0 neu | 11 bekannte Warnungen seit frueheren Laeufen (aelteste besteht seit 1 Tag)", t2)
        self.assertNotIn("   - W0", t2)

    def test_write_speichert_verlauf(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); f = facts(); (d / tb.DATEN).write_text(json.dumps(f))
            tb.write(d, 0, "apply", now=MI)
            v = json.loads((d / tb.VERLAUF).read_text())
            self.assertEqual(set(v["warnungen"]), {"BLOCK empty_order (x.json)", "PO-1"})
            f["warnungen"] = ["PO-1: UNSTIMMIG"]; (d / tb.DATEN).write_text(json.dumps(f))
            tb.write(d, 0, "apply", now=FR)
            self.assertEqual(json.loads((d / tb.VERLAUF).read_text())["warnungen"], {"PO-1": "2026-10-21"})


class Zaehlung(unittest.TestCase):
    def test_mensch_zahl_wie_konsole(self):
        f = facts(); f["mensch"] = {"gesamt": 66, "belege": 45, "ereignisse": 18, "sendungen": 2, "sonstige": 1}
        t = tb.build(f, 0, "apply", now=MI, verlauf={})
        self.assertIn("Mensch entscheidet 66 (wie Konsole): Belege 45 | Ereignisse 18 | Sendungen 2 | Limit/sonstige 1", t)
        self.assertIn("in Klaerfaelle-Tabelle offen 61", t); self.assertNotIn("offen gesamt", t)


class Format(unittest.TestCase):
    def test_kurz_und_vollstaendig(self):
        verlauf = {"tage": {"2026-10-19": 58}, "gesehen": ["m0", "m1"]}
        t = tb.build(facts(), 0, "apply", now=MI, verlauf=verlauf)
        lines = [l for l in t.splitlines() if l.strip()]
        self.assertLessEqual(len(lines), 18)
        self.assertIn("1. Status: OK | Modus: schreibt ins PLM (apply) | Dauer: 7 Min", t)
        self.assertIn("neue Bestellungen 1 | ergaenzte Notizen 12 | Sendungen neu/aktualisiert 1/2 | neue Techpacks 3 | neu gelernte Aliase 1", t)
        self.assertIn("offen gesamt 61 (+3 zum Vortag), neu entstanden: 5", t)   # m0, m1 schon bekannt
        self.assertIn("- Lieferant2: keine Order gefunden 2", t)
        self.assertIn("BLOCK empty_order", t); self.assertIn("UNSTIMMIG", t)
        self.assertIn("26WJD-107 -> PO-LIEFERANT_AA-107", t)
        self.assertNotIn("Stichprobe", t)   # Mittwoch

    def test_mehr_als_fuenf_faelle(self):
        t = tb.build(facts(), 0, "apply", now=MI, verlauf={"tage": {"2026-10-19": 61}, "gesehen": ["x"]})
        self.assertIn("neu entstanden: 7", t); self.assertIn("und 2 weitere", t); self.assertIn("(+0 zum Vortag)", t)

    def test_erstlauf_und_trockenlauf(self):
        f = facts(); f["klaer_offen"] = None
        t = tb.build(f, 0, "dry", now=MI, verlauf={})
        self.assertIn("Trockenlauf", t); self.assertIn("unbekannt (Trockenlauf: 7 Kandidaten)", t); self.assertIn("Erstlauf", t)

    def test_leere_lauf_daten_und_fehler(self):
        t = tb.build({}, 1, "apply", "ABBRUCH bei Sendungen: kaputt", now=MI)
        self.assertIn("1. Status: FEHLER", t); self.assertIn("ABBRUCH bei Sendungen", t); self.assertIn("Keine Lauf-Daten", t)
        t2 = tb.build(None, 0, "dry", now=MI)
        self.assertIn("Keine Lauf-Daten", t2)
        t3 = tb.build({"zahlen": {}, "abbruch": "ABBRUCH: x"}, 0, "apply", now=MI)
        self.assertIn("FEHLER", t3)

    def test_leere_listen(self):
        t = tb.build({"zahlen": {}}, 0, "apply", now=MI, verlauf={"tage": {"2026-10-19": 1}, "gesehen": ["a"]})
        self.assertIn("4. Warnungen: keine", t); self.assertIn("lernte Aliase (Kennung -> Bestellung): keine", t)


class Stichprobe(unittest.TestCase):
    def test_nur_dienstag_und_freitag(self):
        for tag in range(7):
            now = dt.datetime(2026, 10, 19 + tag, 9, 0)
            sp = tb.stichprobe([{"order": "a"}] * 20, now)
            self.assertEqual(sp is not None, tag in (1, 4), tag)

    def test_zehn_zufaellige_und_weniger(self):
        t = tb.build(facts(n_pool=15), 0, "apply", now=DI, verlauf={})
        self.assertIn("Stichprobe", t); self.assertEqual(sum(1 for l in t.splitlines() if l[:3].strip(". ").isdigit() and "| Mail:" in l), 10)
        t2 = tb.build(facts(n_pool=3), 0, "apply", now=FR, verlauf={})
        self.assertEqual(sum(1 for l in t2.splitlines() if "| Mail:" in l), 3)
        t3 = tb.build(facts(n_pool=0), 0, "apply", now=FR, verlauf={})
        self.assertIn("keine Eintraege heute", t3)
        self.assertEqual(tb.stichprobe([{"order": str(i)} for i in range(30)], FR, rng=random.Random(1)), tb.stichprobe([{"order": str(i)} for i in range(30)], FR, rng=random.Random(1)))


class Ablage(unittest.TestCase):
    def test_write_verlauf_und_summary(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d / "tagesdaten.json").write_text(json.dumps(facts()))
            summ = d / "summary.md"
            t = tb.write(d, 0, "apply", now=DI, step_summary=str(summ))
            self.assertEqual((d / "tagesbericht.md").read_text(), t); self.assertIn("Tagesbericht", summ.read_text())
            v = json.loads((d / "tagesbericht_verlauf.json").read_text())
            self.assertEqual(v["tage"]["2026-10-20"], 61); self.assertEqual(len(v["gesehen"]), 7)
            t2 = tb.write(d, 0, "apply", now=MI, step_summary=str(summ))   # naechster Tag: alles bekannt, Veraenderung +0
            self.assertIn("neu entstanden: 0", t2); self.assertIn("(+0 zum Vortag)", t2)

    def test_ohne_daten_schreibt_bericht_ohne_verlauf(self):
        with tempfile.TemporaryDirectory() as d:
            t = tb.write(d, 3, "dry", "Vorabpruefung: nicht eingeloggt", now=MI, step_summary=None)
            self.assertIn("FEHLER", t); self.assertFalse((Path(d) / "tagesbericht_verlauf.json").exists())


if __name__ == "__main__":
    unittest.main()
