import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import phase2_check as pc  # noqa: E402

SRC = "Proforma Invoice XW-SM260710\nBlack 3,500 pcs x 14.00 USD\nTotal USD 70,000.00\nIBAN DE89 3704 0044 0532 0130 00"


def fact(key, value, zitat):
    return {"key": key, "value": value, "src": {"zeile": 1, "zitat": zitat}}


class Quotes(unittest.TestCase):
    def test_ok_in_verschiedenen_schreibweisen(self):
        ex = {"facts": [fact("total", 70000, "Total USD 70,000.00"), fact("qty", 3500, "Black 3,500 pcs x 14.00 USD"), fact("price", 14, "Black 3,500 pcs x 14.00 USD")]}
        self.assertEqual(pc.check_quotes(ex, SRC), ([], 0))

    def test_zitat_nicht_in_quelle(self):
        e, _ = pc.check_quotes({"facts": [fact("total", 70000, "Total USD 80,000.00")]}, SRC)
        self.assertTrue(e and "nicht wörtlich" in e[0])

    def test_wert_nicht_im_zitat(self):
        e, _ = pc.check_quotes({"facts": [fact("total", 7000, "Total USD 70,000.00")]}, SRC)
        self.assertTrue(e and "nicht im Zitat" in e[0])

    def test_teilzahl_zaehlt_nicht(self):
        e, _ = pc.check_quotes({"facts": [fact("x", 500, "Black 3,500 pcs x 14.00 USD")]}, SRC)
        self.assertTrue(e)

    def test_ohne_zitat_und_null(self):
        e, n = pc.check_quotes({"facts": [{"key": "a", "value": 5}, {"key": "b", "value": None, "fehlt_grund": "nicht im Beleg"}]}, SRC)
        self.assertEqual((len(e), n), (1, 1))


class Sums(unittest.TestCase):
    def test_summen_ok_und_falsch(self):
        o = {"order": {"total": 70000, "pieces": 5000, "items": [{"qty": 3500, "price": 14, "sum": 49000}, {"qty": 1500, "price": 14, "sum": 21000}],
                       "payments": [{"amount": 21000}, {"amount": 49000}]}}
        self.assertEqual(pc.check_sums(o), [])
        o["order"]["payments"][1]["amount"] = 48000
        self.assertEqual(len(pc.check_sums(o)), 1)
        o["order"]["items"][0]["sum"] = 50000
        self.assertTrue(any("Positionen" in e for e in pc.check_sums(o)))


class Masse(unittest.TestCase):
    def test_groessen_und_monotonie(self):
        m = {"measurements": {"sizes": ["S", "M", "L"], "rows": [{"name": "Brust", "values": {"S": 50, "M": 52, "L": 54}}, {"name": "Länge", "values": {"S": 60, "M": 58, "L": 62}}]}}
        e = pc.check_measurements(m, ["S", "M", "L"])
        self.assertEqual(len(e), 1)
        self.assertTrue(pc.check_measurements(m, ["S", "M"]))

    def test_zusammensetzung(self):
        self.assertEqual(pc.check_composition({"composition": [{"percent": 80}, {"percent": 20}]}), [])
        self.assertTrue(pc.check_composition({"composition": [{"percent": 80}, {"percent": 10}]}))


class Bank(unittest.TestCase):
    def test_bank_in_feld_aber_nicht_im_zitat(self):
        self.assertTrue(pc.check_bank({"notes": "IBAN DE89 3704 0044 0532 0130 00"}))
        self.assertEqual(pc.check_bank({"facts": [{"key": "k", "value": 1, "src": {"zeile": 4, "zitat": "IBAN DE89 3704 0044 0532 0130 00"}}]}), [])


class Cross(unittest.TestCase):
    def test_abweichung(self):
        a = {"facts": [fact("total", 70000, "x"), fact("qty", 3500, "x")]}
        b = {"facts": [fact("total", 70000.0, "x"), fact("qty", 3600, "x")]}
        e = pc.cross(a, b)
        self.assertEqual(len(e), 1)
        self.assertIn("qty", e[0])


class Lauf(unittest.TestCase):
    def test_verzeichnislauf(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "lief"
            for s in ("src", "extract", "check"):
                (d / s).mkdir(parents=True)
            (d / "src" / "f1.txt").write_text(SRC)
            ex = {"facts": [fact("total", 70000, "Total USD 70,000.00")], "order": {"total": 70000}}
            (d / "extract" / "f1.json").write_text(json.dumps(ex))
            (d / "check" / "f1.json").write_text(json.dumps(ex))
            self.assertEqual(pc.run(d, True)[0], 0)
            ex["facts"][0]["value"] = 71000
            (d / "check" / "f1.json").write_text(json.dumps(ex))
            self.assertGreater(pc.run(d, True)[0], 0)


if __name__ == "__main__":
    unittest.main()
