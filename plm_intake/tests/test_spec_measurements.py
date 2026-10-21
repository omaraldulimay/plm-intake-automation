import sys
import unittest
from pathlib import Path
from pathlib import PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import spec_measurements as sm  # noqa: E402

GRID = [
    ["Size chart UOM: CM"],
    [None, "Measurement", "XS", "S", "M", "L", "XL", "XXL", "Tol"],
    ["FL", "Front length", "62,00", "63,5", 65, 66.5, 68, 69.5, "+/-1"],
    ["CW", "1/2 Chest", 56, 58, 60, 62, 64, 66, "+/-1,5"],
    ["NDB", "Neck drop back", 2, 2, 2, 2, 2, 2, None],
]
PDF = ("SIZE RANGE\nS\nM\nL\nNo\nSPEC\nDescription\nFLH\nFRONT LENGTH fm HSP\n72\n74\n76\n+/-1,0\n"
       "C\n1/2 CHEST WIDTH\n57\n59\n61\n+/-1,0\n")


def prod(pid, sku, sizes):
    return {"id": pid, "sku": sku, "name": "N " + sku, "sizes": sizes}


class Parsing(unittest.TestCase):
    def test_xlsx_gitter(self):
        t = sm.parse_grid(GRID)[0]
        self.assertEqual(t["sizes"], ["XS", "S", "M", "L", "XL", "2XL"])   # XXL = 2XL
        r = t["rows"][0]
        self.assertEqual((r["name"], r["code"], r["tol"]), ("Front length", "FL", "+/-1"))
        self.assertEqual(r["values"]["XS"], 62.0)                          # Komma als Dezimaltrenner
        self.assertEqual(t["unit"], "cm")

    def test_pdf_text(self):
        t = sm.parse_pdf_text([PDF])[0]
        self.assertEqual(t["sizes"], ["S", "M", "L"])
        self.assertEqual([(r["code"], r["name"], r["values"]["L"], r["tol"]) for r in t["rows"]],
                         [("FLH", "FRONT LENGTH fm HSP", 76.0, "+/-1,0"), ("C", "1/2 CHEST WIDTH", 61.0, "+/-1,0")])

    def test_zufalls_kopf_wird_ignoriert(self):
        g = [["Maße", "S", "M", "L"], ["a", 1, 2, 3], ["Grade", None, "S-XL", "XXL-XXXL"], ["b", 4, 5, 6]]
        self.assertEqual([t["sizes"] for t in sm.parse_grid(g)], [["S", "M", "L"]])


class Plausibel(unittest.TestCase):
    def test_monotonie(self):
        t = sm.parse_grid(GRID)[0]
        self.assertEqual(sm.monotone_check(t), [])
        t["rows"][1]["values"]["L"] = 50      # fällt deutlich
        bad = sm.monotone_check(t)
        self.assertEqual(len(bad), 1)
        self.assertFalse(bad[0]["small"])
        a = sm.assess(t, ["XS", "S", "M", "L", "XL", "XXL"])
        self.assertEqual(a["status"], "auffaellig")

    def test_kleine_ausnahme_ist_nur_hinweis(self):
        t = sm.parse_grid(GRID)[0]
        t["rows"][0]["values"]["L"] = 64.8    # 0.2 cm Rückgang
        a = sm.assess(t, ["XS", "S", "M", "L", "XL", "XXL"])
        self.assertEqual(a["status"], "ok")
        self.assertTrue(any("kleiner Rückgang" in x for x in a["issues"]))

    def test_unplausible_werte_und_inch(self):
        t = sm.parse_grid(GRID)[0]
        t["rows"][0]["values"]["S"] = -3
        self.assertEqual(sm.assess(t, ["S"])["status"], "unplausibel")
        g = [["Size chart (inch)"], ["x", "S", "M"], ["Chest", 20, 21]]
        a = sm.assess(sm.parse_grid(g)[0], ["S", "M"])
        self.assertEqual(a["table"]["rows"][0]["values"]["S"], 50.8)       # eindeutig inch -> x2.54


class Groessenabgleich(unittest.TestCase):
    def test_xxl_gleich_2xl_und_fehlende(self):
        m, miss = sm.match_sizes(["S", "M", "2XL", "3XL"], ["S", "M", "XXL"])
        self.assertEqual(m, {"S": "S", "M": "M", "2XL": "XXL"})            # Schreibweise des Produkts
        self.assertEqual(miss, ["3XL"])

    def test_one_size_blockiert(self):
        a = sm.assess(sm.parse_grid(GRID)[0], ["ONE SIZE"])
        self.assertEqual(sm.classify(prod("1", "A", ["ONE SIZE"]), a, False)[0], "blockiert")


class Build(unittest.TestCase):
    Z = [
        {"typ": "Spec", "name": "a", "datei": "2026-05-01_x_A size chart.xlsx", "datum": "2026-05-01", "ids": ["1", "2"], "skus": []},
        {"typ": "Spec", "name": "a", "datei": "2026-08-01_x_A size chart.xlsx", "datum": "2026-08-01", "ids": ["1", "2"], "skus": []},
        {"typ": "Spec", "name": "p", "datei": "2026-07-03_x_561872_2510_Anlage_Verpackungsmasse_1.xlsm", "datum": "2026-07-03", "ids": ["1"], "skus": []},
    ]
    P = [prod("1", "A1", ["XS", "S", "M", "L", "XL", "XXL"]), prod("2", "A2", ["XS", "S", "M", "L", "XL", "XXL"])]

    def run_build(self, inv, fresh=None):
        gelesen = []

        def reader(path):
            gelesen.append(PurePosixPath(str(path)).name)
            t = sm.parse_grid(GRID)
            t[0]["sheet"] = "S1"
            return t, None
        r = sm.build(self.Z, self.P, inv, fresh, reader=reader)
        return r, gelesen

    def test_vorhandene_masse_werden_nicht_angefasst(self):
        r, _ = self.run_build({"1": {"masse": True}, "2": {"masse": False}})
        st = {x["sku"]: x for x in r["plan"]}
        self.assertEqual(st["A1"]["status"], "vorhanden")
        self.assertNotIn("lines", st["A1"])                                 # nichts zu schreiben
        self.assertEqual(st["A2"]["status"], "schreiben")
        self.assertEqual(len(st["A2"]["lines"]), 3 * 6)
        self.assertEqual(st["A2"]["lines"][0], {"productSku": "A2", "productName": "N A2", "pom": "Front length", "size": "XS", "value": "62", "unit": "cm"})

    def test_frische_ruecklesung_sperrt(self):
        r, _ = self.run_build({"1": {"masse": False}, "2": {"masse": False}}, fresh={"2": True})
        self.assertEqual({x["sku"]: x["status"] for x in r["plan"]}, {"A1": "schreiben", "A2": "vorhanden"})

    def test_nur_neueste_fassung_und_verpackung_getrennt(self):
        r, gelesen = self.run_build({})
        self.assertEqual(gelesen, ["2026-08-01_x_A size chart.xlsx"])      # ältere Fassung + Verpackungsdatei nicht gelesen
        self.assertEqual(len(r["plan"][0]["aeltere_fassungen"]), 1)
        self.assertEqual(len(r["verpackung"]), 1)


if __name__ == "__main__":
    unittest.main()
