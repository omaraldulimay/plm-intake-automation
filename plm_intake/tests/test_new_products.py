import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import new_products as npd  # noqa: E402

def pr(i, sku, name, col=None, cat=None):
    d = {"id": i, "sku": sku, "name": name}
    if col: d["collection"] = {"name": col}; d["category"] = {"name": cat}
    return d


PRODUCTS = [pr("P1", "HY29582", "Alt Half Zip"), pr("P2", "SKM27-001", "Smilodox Hoodie", "Hoodie", "HOO – Hoodie / Kapuzenpullover"),
            pr("P3", "A1", "x", "Outerwear", "JAC – Jacke"), pr("P4", "A2", "x", "Outerwear", "JAC – Jacke"), pr("P5", "A3", "x", "Sonderjacken", "JAC – Jacke"),
            pr("P6", "A4", "x", "Hosen", "PNT – Hose (Schlaghose, Capri)"), pr("P7", "A5", "x", "Jogginghosen", "JOG – Jogginghose / Trainingshose"),
            pr("P8", "A6", "x", "Leggings", "LEG – Leggings / Tights"), pr("P9", "A7", "x", "Sweatshirt", "SWE – Sweatshirt / Pullover"), pr("P10", "A8", "x", "Accessoires", "CAP – Cap / Mütze"),
            pr("P11", "A9", "x", "Uncategorized", "General")]
VENDOR = {"id": "V1", "name": "Kyle"}


def po(*items): return {"vendor": "Kyle", "items": list(items)}
def it(sku, name="MEN'S JACKET", colors=("Black",), sizes=("M", "L"), **pi):
    return {"sku": sku, "name": name, "product_info": pi, "variants": [{"color": c, "price": 5, "sizes": {s: 1 for s in sizes}} for c in colors]}


class Planung(unittest.TestCase):
    def test_neuer_style_bekommt_vorlaeufige_sku_tags_und_kategorie(self):
        sp, sk = npd.plan_products(po(it("ZZ-100", "MEN'S JACKET", ("Black", "Navy"))), VENDOR, PRODUCTS)
        self.assertEqual(len(sp), 1); s = sp[0]
        self.assertEqual((s["sku"], s["collection"], s["category"], s["category_code"], s["sizes"], s["colors"]),
                         ("ZZ-100", "Outerwear", "JAC – Jacke", "JAC", ["M", "L"], ["Black", "Navy"]))
        self.assertIn("SKU-OFFEN", s["tags"]); self.assertEqual(s["vendor"], "Kyle"); self.assertTrue(s["name"].startswith("ZZ-100 "))

    def test_vorhandene_produkte_werden_nie_neu_angelegt(self):
        sp, sk = npd.plan_products(po(it("HY29582"), it("hy-29582")), VENDOR, PRODUCTS)
        self.assertEqual(sp, [])

    def test_variante_eines_vorhandenen_basisstyles_geht_zum_menschen(self):
        sp, sk = npd.plan_products(po(it("HY29582-Z-A")), VENDOR, PRODUCTS)
        self.assertEqual(sp, []); self.assertIn("Mensch entscheidet", sk[0][1])

    def test_style_alias_verhindert_dublette(self):
        sp, _ = npd.plan_products(po(it("ALP-108-26")), VENDOR, PRODUCTS, {"ALP-108-26": "P2"})
        self.assertEqual(sp, [])

    def test_ohne_stylenummer_kein_produkt(self):
        sp, sk = npd.plan_products(po(it("")), VENDOR, PRODUCTS); self.assertEqual(sp, []); self.assertIn("ohne Stylenummer", sk[0][1])

    def test_ohne_groessenverteilung_one_size_und_ohne_farbe_keine_variante(self):
        i = it("ZZ-5", colors=(), sizes=()); i["variants"] = [{"color": None, "price": 1, "quantity": 5, "sizes": {}}]
        s = npd.plan_products(po(i), VENDOR, PRODUCTS)[0][0]; self.assertEqual((s["sizes"], s["colors"]), (["ONE SIZE"], []))

    def test_doppelter_style_in_einer_po_nur_einmal_und_limit(self):
        sp, _ = npd.plan_products(po(it("ZZ-1"), it("zz-1")), VENDOR, PRODUCTS); self.assertEqual(len(sp), 1)
        many = po(*[it("QQ-%d" % i) for i in range(12)])
        sp, sk = npd.plan_products(many, VENDOR, PRODUCTS, limit=8); self.assertEqual((len(sp), len(sk)), (8, 4))

    def test_barcode_nur_wenn_gueltige_ean(self):
        ok = npd.plan_products(po(it("ZZ-7", barcode="4006381333931")), VENDOR, PRODUCTS)[0][0]
        bad = npd.plan_products(po(it("ZZ-8", barcode="4012345678904")), VENDOR, PRODUCTS)[0][0]
        self.assertEqual(ok["barcode"], "4006381333931"); self.assertIsNone(bad["barcode"])

    def test_einsortierung_in_bestehende_collections_nie_neu_erfinden(self):
        for name, col, cat in (("BAYAN TAYT", "Leggings", "LEG – Leggings / Tights"), ("KADIN SWEAT", "Sweatshirt", "SWE – Sweatshirt / Pullover"),
                               ("KADIN EŞOFMAN ALTI", "Jogginghosen", "JOG – Jogginghose / Trainingshose"), ("Men Hoodie Regular", "Hoodie", "HOO – Hoodie / Kapuzenpullover"),
                               ("Men's Long Pant", "Hosen", "PNT – Hose (Schlaghose, Capri)"), ("Bucket Hat", "Accessoires", "CAP – Cap / Mütze")):
            c, k, code, sure = npd.resolve_target(name, PRODUCTS)
            self.assertEqual((c, k, sure), (col, cat, True), name)
        used = {npd.resolve_target(n, PRODUCTS)[0] for n in ("Jacket", "Parka", "Windbreaker")}
        self.assertEqual(used, {"Outerwear"})   # haeufigste Collection fuer JAC (2x Outerwear gegen 1x Sonderjacken)

    def test_unbekannter_typ_oder_fehlende_kategorie_geht_nach_uncategorized_mit_tag(self):
        self.assertEqual(npd.resolve_target("Irgendwas Neues", PRODUCTS)[:3], ("Uncategorized", "General", None))
        sp, _ = npd.plan_products(po(it("ZZ-77", "Mystery Item")), VENDOR, PRODUCTS)
        self.assertIn("KATEGORIE-OFFEN", sp[0]["tags"]); self.assertEqual((sp[0]["collection"], sp[0]["category"]), ("Uncategorized", "General"))
        sp2, _ = npd.plan_products(po(it("ZZ-78", "MEN'S JACKET")), VENDOR, [])   # leeres PLM: keine Collection erfinden
        self.assertEqual((sp2[0]["collection"], sp2[0]["category"]), ("Uncategorized", "General"))

    def test_kategorie_code_geht_ins_feld(self):
        sp, _ = npd.plan_products(po(it("ZZ-79", "MEN'S HOODIE")), VENDOR, PRODUCTS)
        self.assertEqual(npd.field_patch(sp[0], {"updatedAt": "T"})["customFields"][npd.KATCODE_KEY], "HOO")

    def test_csv_hat_collection_vendor_tags_und_kein_main_material(self):
        sp, _ = npd.plan_products(po(it("ZZ-9", colors=("Black", "Navy"))), VENDOR, PRODUCTS)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.csv"; npd.write_csv(sp, f); r = list(csv.DictReader(open(f, encoding="utf-8")))[0]
        self.assertEqual((r["Collection"], r["SKU"], r["Main Vendor"], r["Main Material"], r["Variants"]), ("Outerwear", "ZZ-9", "Kyle", "", "Black, Navy"))
        self.assertIn("SKU-OFFEN", r["Tags"])


class Felder(unittest.TestCase):
    def test_patch_merged_vorhandene_custom_fields_und_setzt_barcode(self):
        spec = {"uvp": 39.9, "purchase_price": 12.5, "barcode": "4006381333931"}
        b = npd.field_patch(spec, {"customFields": {"anderes": "x"}, "updatedAt": "T"})
        self.assertEqual(b["customFields"], {"anderes": "x", npd.UVP_KEY: 39.9, npd.EK_KEY: 12.5}); self.assertEqual((b["barcode"], b["expectedUpdatedAt"]), ("4006381333931", "T"))

    def test_nichts_zu_schreiben_ist_none_und_text_preise_werden_ignoriert(self):
        self.assertIsNone(npd.field_patch({"uvp": None, "purchase_price": None, "barcode": None}, {"updatedAt": "T"}))
        self.assertIsNone(npd.field_patch({"uvp": "viel", "purchase_price": True}, {"updatedAt": "T"}))


if __name__ == "__main__":
    unittest.main()
