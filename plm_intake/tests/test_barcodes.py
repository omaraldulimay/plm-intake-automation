import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import barcodes as bc  # noqa: E402

E1, E2, E3 = "4062517472110", "4062517472127", "4062517472134"   # gueltige EAN-13


def cell(v, s, b="", sku="", color=None):
    return {"variant": v, "color": color or v, "size": s, "barcode": b, "sku": sku, "iid": "I-" + v, "sid": "S-" + s}


def prow(vn, color, size, ean):
    return {"variation_no": vn, "color": color, "size": size, "ean": ean}


class Plan(unittest.TestCase):
    def test_ean_pruefung(self):
        self.assertTrue(bc.ean_ok(E1)); self.assertFalse(bc.ean_ok("4062517472111")); self.assertFalse(bc.ean_ok("123")); self.assertFalse(bc.ean_ok(""))

    def test_leere_zellen_werden_mit_ean_und_sku_gefuellt_farbe_de_en_und_groesse(self):
        cells = [cell("Black", "S"), cell("Black", "M"), cell("Black", "L")]
        pr = [prow("AL29008-A1", "Schwarz", "S", E1), prow("AL29008-A2", "Schwarz", "M", E2), prow("AL29008-A3", "Schwarz", "L", E3)]
        pl = bc.plan_product(pr, cells, {})
        self.assertEqual(len(pl["rows"]), 3); self.assertEqual(pl["rows"][0], {"variantName": "Black", "sizeTitle": "S", "identifierId": "I-Black", "sizeId": "S-S", "barcode": E1, "sku": "AL29008-A1"})
        self.assertEqual((pl["conflicts"], pl["missing"], pl["dup"], pl["bad_ean"]), ([], [], [], []))

    def test_vorhandene_gleiche_werte_werden_nicht_neu_geschrieben_abweichende_sind_konflikte(self):
        cells = [cell("Black", "S", E1, "AL29008-A1"), cell("Black", "M", "4062517472999", ""), cell("Black", "L", "", "FALSCH")]
        pr = [prow("AL29008-A1", "Schwarz", "S", E1), prow("AL29008-A2", "Schwarz", "M", E2), prow("AL29008-A3", "Schwarz", "L", E3)]
        pl = bc.plan_product(pr, cells, {})
        self.assertEqual(len(pl["conflicts"]), 2)   # M: andere EAN; L: andere SKU
        rows = {(r["variantName"], r["sizeTitle"]): r for r in pl["rows"]}
        self.assertNotIn(("Black", "S"), rows)                          # nichts zu tun
        self.assertEqual(rows[("Black", "M")]["barcode"], None)         # EAN wird NIE ueberschrieben
        self.assertEqual(rows[("Black", "M")]["sku"], "AL29008-A2")     # leere SKU darf gefuellt werden
        self.assertEqual(rows[("Black", "L")]["barcode"], E3); self.assertIsNone(rows[("Black", "L")]["sku"])

    def test_fehlende_zelle_ungueltige_ean_und_dublette(self):
        cells = [cell("Black", "S")]
        pr = [prow("X-A1", "Schwarz", "S", E1), prow("X-A2", "Schwarz", "M", E2), prow("X-B1", "Schwarz", "S", "4062517472111")]
        pl = bc.plan_product(pr, cells, {})
        self.assertEqual(len(pl["rows"]), 1); self.assertEqual(len(pl["missing"]), 1); self.assertEqual(len(pl["bad_ean"]), 1)
        pl2 = bc.plan_product([prow("X-A1", "Schwarz", "S", E1)], cells, {E1: "anderes_produkt"})
        self.assertEqual(pl2["rows"], []); self.assertEqual(len(pl2["dup"]), 1)   # EAN gehoert schon einem anderen Produkt
        pl3 = bc.plan_product([prow("X-A1", "Schwarz", "S", E1), prow("X-A9", "Schwarz", "S", E1)], cells, {})
        self.assertEqual(len(pl3["rows"]), 1); self.assertEqual(len(pl3["dup"]), 1)  # gleiche EAN zweimal in Plenty

    def test_mehrdeutige_zelle_wird_nicht_geraten(self):
        cells = [cell("Black", "S"), cell("Black ", "S", color="Schwarz")]
        pl = bc.plan_product([prow("X-A1", "Schwarz", "S", E1)], cells, {})
        self.assertEqual(pl["rows"], []); self.assertIn("Zellen passen", pl["missing"][0][3])

    def test_groessen_schreibweisen(self):
        self.assertEqual((bc.norm_size("xxl"), bc.norm_size("3XL"), bc.norm_size("One Size")), ("XXL", "3XL", "ONESIZE"))
        self.assertEqual(bc.parse_attrs("Size:XS, Color:Bordeaux"), {"size": "XS", "color": "Bordeaux"})


if __name__ == "__main__":
    unittest.main()


class Farbschluessel(unittest.TestCase):
    def test_gleiche_farben_in_verschiedenen_schreibweisen(self):
        k = bc.colour_key
        self.assertEqual(k("Dunkel Blau"), k("Dark Blue")); self.assertEqual(k("Dark Blue"), k("Dunkelblau")); self.assertEqual(k("Major Brown"), k("Braun"))
        self.assertEqual(k("Flieder / Nirvana 17-3808 TCX"), k("Flieder")); self.assertEqual(k("AN-43 Flared Leggings - Bordeaux"), k("Bordeaux"))
        self.assertEqual(k("Black"), k("Schwarz")); self.assertEqual(k("Navy"), k("Dunkelblau"))

    def test_verschiedene_farben_bleiben_verschieden(self):
        k = bc.colour_key
        self.assertNotEqual(k("Hellgrau"), k("Grau")); self.assertNotEqual(k("Grau Melange"), k("Grau")); self.assertNotEqual(k("Royal Blau"), k("Dunkelblau"))
        self.assertNotEqual(k("Schwarz"), k("Braun")); self.assertNotEqual(k("Anthrazit"), k("Grau"))


class PaspelUndKollision(unittest.TestCase):
    def test_paspel_farbe_gehoert_zum_schluessel(self):
        k = bc.colour_key
        self.assertNotEqual(k("Schwarz piping black"), k("Schwarz piping white")); self.assertEqual(k("Schwarz piping white"), k("Schwarz Piping White"))
        self.assertNotEqual(k("Hellblau piping white"), k("Hellblau"))

    def test_zwei_plenty_zeilen_auf_eine_zelle_werden_nicht_geschrieben(self):
        cells = [cell("Hellblau", "S")]
        pr = [prow("X-A1", "Hellblau", "S", E1), prow("X-B1", "Hellblau", "S", E2)]
        pl = bc.plan_product(pr, cells, {})
        self.assertEqual(pl["rows"], []); self.assertTrue(any("Kollision" in m[3] or "Zellen" in m[3] for m in pl["missing"]))


class PaspelHauptfarbe(unittest.TestCase):
    def test_hauptfarbe_ist_der_teil_vor_dem_paspelzusatz(self):
        k = bc.colour_key
        self.assertNotEqual(k("Hellblau piping white"), k("Weiß")); self.assertNotEqual(k("Hellblau piping white"), k("Hellblau"))
        self.assertNotEqual(k("Hellblau piping white"), k("Hellblau piping blue")); self.assertEqual(k("Hellblau piping white")[0], "blue")
        self.assertEqual(k("Hellgrün"), k("Hell Grün")); self.assertEqual(k("Dunkelbraun")[:2], ("brown", "dark"))


class Varianten(unittest.TestCase):
    from plm_intake import variants as vr

    def test_neue_farbe_und_blockierte_groesse(self):
        vr = self.vr
        cells = [cell("Black", "S"), cell("Black", "M")]
        missing = [("X-A3", "Schwarz", "L", "keine Zelle"), ("X-B1", "Grau", "S", "keine Zelle"), ("X-B2", "Grau", "M", "keine Zelle"), ("X-C1", "Grau", "3XL", "keine Zelle"), ("X-D1", "Blau", "S", "2 Zellen passen")]
        new, blocked = vr.plan_variants(missing, cells, ["S", "M", "L"])
        self.assertEqual([(v["name"], v["sizes"], v["missing_sizes"]) for v in new], [("Grau", ["3XL", "M", "S"], ["3XL"])])   # Schwarz existiert schon -> nur Groesse blockiert
        self.assertEqual(len(blocked), 1); self.assertIn("Groesse fehlt", blocked[0][3])                                     # '2 Zellen passen' wird nie als neue Farbe geplant

    def test_bibliotheksfarbe_nur_mit_hex_und_eindeutig(self):
        vr = self.vr
        opts = [{"id": "1", "name": "Grau", "hex": "#888888", "colorType": "MyColor"}, {"id": "2", "name": "Grau Melange", "hex": None, "colorType": "MyColor"}]
        self.assertEqual(vr.pick_color(opts, "Grau")[0]["id"], "1")
        self.assertIsNone(vr.pick_color(opts, "Grau Melange")[0]); self.assertIn("ohne Hex", vr.pick_color(opts, "Grau Melange")[1])
        self.assertIsNone(vr.pick_color(opts + [{"id": "3", "name": "grau", "hex": "#777777", "colorType": "MyColor"}], "Grau")[0])
        self.assertIn("keine Bibliotheksfarbe", vr.pick_color([], "Rosa")[1])


class HsCode(unittest.TestCase):
    from plm_intake import packaging as pk

    def test_plausibilitaet_und_regeln(self):
        pk = lieferant-extra.example
        self.assertEqual(pk.plan({"name": "XW-124 Men Jacket"}, {"61013090"}, None)[0], "SCHREIBEN")
        self.assertEqual(pk.plan({"name": "F-3 leggings"}, {"64029998"}, None)[0], "FLAGGE")             # Schuh-Code an Bekleidung
        self.assertEqual(pk.plan({"name": "GT0301 Bag 50x35x15 cm"}, {"64029998"}, None)[0], "FLAGGE")    # Schuh-Code an Tasche
        self.assertEqual(pk.plan({"name": "GT0302 Bag"}, {"42029291"}, None)[0], "SCHREIBEN")
        self.assertEqual(pk.plan({"name": "Sneaker WHITE"}, {"64041100"}, None)[0], "SCHREIBEN")
        self.assertEqual(pk.plan({"name": "X Jacket"}, {"61013090", "61099020"}, None)[0], "FLAGGE")      # widerspruechlich
        self.assertEqual(pk.plan({"name": "X Jacket"}, {"61013090"}, "6101.30.90")[0], "OK")              # schon gesetzt, gleich
        self.assertEqual(pk.plan({"name": "X Jacket"}, {"61013090"}, "62019300")[0], "KONFLIKT")          # nie ueberschreiben
        self.assertEqual(pk.plan({"name": "X Jacket"}, set(), None)[0], "KEIN_PLENTY")
        self.assertEqual(pk.plan({"name": "HY29582 Performance Jacket"}, {"61099020"}, None)[0], "FLAGGE")   # T-Shirt-Position an Jacke
        self.assertEqual(pk.plan({"name": "XW26-006 Men T Shirt"}, {"61099020"}, None)[0], "SCHREIBEN")
        self.assertEqual(pk.plan({"name": "AN-43 Flared leggings"}, {"61046300"}, None)[0], "SCHREIBEN")
        self.assertEqual(pk.plan({"name": "AL29008"}, {"61034200"}, None)[0], "SCHREIBEN")                    # kein Stichwort: nur Kapitel zaehlt


class AttributNamen(unittest.TestCase):
    def test_abweichende_attributnamen_werden_erkannt(self):
        self.assertEqual(bc.parse_attrs("Couch color:Schwarz, Größe:S"), {"color": "Schwarz", "size": "S"})
        self.assertEqual(bc.parse_attrs("Size:XS, Color:Bordeaux"), {"size": "XS", "color": "Bordeaux"})
        self.assertEqual(bc.parse_attrs("Farbe:Rot, Groesse:M"), {"color": "Rot", "size": "M"})

    def test_leerer_farbname_erzeugt_keine_variante(self):
        from plm_intake import variants as vr
        new, _ = vr.plan_variants([("X-A1", "", "S", "keine Zelle"), ("X-B1", "  ", "M", "keine Zelle")], [], ["S", "M"])
        self.assertEqual(new, [])
