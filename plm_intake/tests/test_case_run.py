import copy
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import case_run as cr  # noqa: E402

CASE = {"key": "T", "vendor": {"name": "V"}, "collection": "C", "category": "General",
        "colors": [{"name": "Black", "hex": "#000000", "code": "B"}, {"name": "Navy", "hex": "#001f3f", "code": "N"}],
        "material": {"name": "Fleece", "type": "MATERIALS", "category": "Knit Fabrics"}, "trims": [{"name": "Zip", "category": "Zippers"}],
        "product": {"name": "H1", "sku": "S1", "sizes": ["S", "M"], "year": "2026", "barcode": "4006381333931", "uvp": 49.9, "measurements": [{"name": "Chest", "code": "A", "value": "56", "tol": "1"}], "status": "Production", "costing_rrp": 49.9},
        "po": {"title": "T PO", "price": 10, "lines": [{"color": "Black", "sizes": {"M": 5}}], "payments": []}}
IDS = {"material": "MAT", "trims": {"Zip": "ZIP"}}


class Normalisierung(unittest.TestCase):
    def test_kurzform_wird_mehrprodukt(self):
        c = cr.normalize(copy.deepcopy(CASE))
        self.assertEqual(len(c["products"]), 1); self.assertEqual(c["po"]["items"][0]["sku"], "S1"); self.assertEqual(c["products"][0]["colors"], ["Black", "Navy"])

    def test_zwei_produkte_zwei_positionen(self):
        c = copy.deepcopy(CASE); c["products"] = [c.pop("product"), dict(name="H2", sku="S2", sizes=["L"], colors=["Navy"])]
        c["po"] = {"title": "T PO", "payments": [], "items": [{"sku": "S1", "price": 10, "lines": []}, {"sku": "S2", "price": 12, "lines": []}]}
        self.assertEqual(len(cr.normalize(c)["products"]), 2)

    def test_doppelte_sku_und_unbekannte_position_brechen_ab(self):
        c = copy.deepcopy(CASE); c["products"] = [c.pop("product"), dict(name="H2", sku="S1", sizes=["L"])]
        c["po"] = {"title": "T", "payments": [], "items": [{"sku": "S1", "price": 1, "lines": []}]}
        with self.assertRaises(SystemExit): cr.normalize(c)
        c2 = copy.deepcopy(CASE); c2["po"] = {"title": "T", "payments": [], "items": [{"sku": "XX", "price": 1, "lines": []}]}
        with self.assertRaises(SystemExit): cr.normalize(c2)


class Ausgaben(unittest.TestCase):
    def test_csv_eine_zeile_je_produkt_ohne_main_material(self):
        c = copy.deepcopy(CASE); c["products"] = [c.pop("product"), dict(name="H2", sku="S2", sizes=["L"], colors=["Navy"])]
        c["po"] = {"title": "T", "payments": [], "items": [{"sku": "S1", "price": 1, "lines": []}, {"sku": "S2", "price": 1, "lines": []}]}
        cr.normalize(c)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.csv"; cr.products_csv(c, f)
            rows = list(csv.DictReader(open(f, encoding="utf-8")))
        self.assertEqual([r["SKU"] for r in rows], ["S1", "S2"]); self.assertEqual(rows[1]["Variants"], "Navy"); self.assertTrue(all(r["Main Material"] == "" for r in rows))

    def test_phase2_enthaelt_bom_trims_sample_status_costing(self):
        c = cr.normalize(copy.deepcopy(CASE)); acts = cr.phase2_for(c, c["products"][0], "PID", "VID", IDS)
        tools = [a["tool"] for a in acts]
        self.assertEqual(tools, ["update_product", "manage_base_measurements", "add_bom_component", "add_bom_component", "start_product_sampling_round", "update_product_status", "create_costing_scenario"])
        self.assertTrue(acts[2]["input"]["mainMaterial"]); self.assertEqual(acts[2]["input"]["libraryId"], "MAT"); self.assertEqual(acts[3]["input"]["libraryId"], "ZIP")

    def test_bei_mehreren_produkten_keine_einzel_sample_runde(self):
        c = copy.deepcopy(CASE); c["products"] = [c.pop("product"), dict(name="H2", sku="S2", sizes=["L"], colors=["Navy"])]
        c["po"] = {"title": "T", "payments": [], "items": [{"sku": "S1", "price": 1, "lines": []}, {"sku": "S2", "price": 1, "lines": []}]}
        c = cr.normalize(c)
        self.assertNotIn("start_product_sampling_round", [a["tool"] for a in cr.phase2_for(c, c["products"][0], "P", "V", IDS)])

    def test_phase2_ohne_optionale_angaben_schreibt_nichts_ueberfluessiges(self):
        c = copy.deepcopy(CASE); c["product"] = dict(name="H", sku="S", sizes=["M"]); c = cr.normalize(c)
        tools = [a["tool"] for a in cr.phase2_for(c, c["products"][0], "PID", "VID", IDS)]
        self.assertNotIn("update_product", tools); self.assertNotIn("manage_base_measurements", tools); self.assertNotIn("create_costing_scenario", tools)


if __name__ == "__main__":
    unittest.main()
