import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import techpack_map as tm  # noqa: E402

P = [{"id": "a", "sku": "SDKM260051"}, {"id": "b", "sku": "SDKM260061"}, {"id": "c", "sku": "561872"}, {"id": "d", "sku": "SNM26008"},
     {"id": "e", "sku": "XW-042-CROC"}, {"id": "f", "sku": "XW-042-CHET"}, {"id": "g", "sku": "XW26-006"}]
AL = {tm.nk("SLM26-001"): "561872"}


class Zuordnung(unittest.TestCase):
    def ids(self, r):
        return sorted(p["id"] for p in r[0])

    def test_exakt(self):
        self.assertEqual(self.ids(tm.resolve("XW26-006_TP.pdf", P, AL)), ["g"])

    def test_kunde_y_regel(self):
        r = tm.resolve("SKM26-005_TP_Men's Hood Black.pdf", P, AL)
        self.assertEqual((self.ids(r), r[1]), (["a"], "regel"))
        self.assertEqual(self.ids(tm.resolve("SKM26-006-1_TP.pdf", P, AL)), ["b"])

    def test_alias(self):
        r = tm.resolve("TP_Spec SLM26-001_Men's T-Shirt.pdf", P, AL)
        self.assertEqual((self.ids(r), r[1]), (["c"], "alias"))

    def test_datei_alias(self):
        al = {tm.nk("Dawson_BOM_MC.pdf"): "SNM26-008"}
        r = tm.resolve("Dawson_BOM_MC.pdf", P, al)
        self.assertEqual((self.ids(r), r[1]), (["d"], "alias"))
        self.assertEqual(tm.resolve("Andere_BOM_MC.pdf", P, al)[1], "offen")

    def test_mehrere_styles(self):
        self.assertEqual(self.ids(tm.resolve("SKM26-005+SKM26-006_TP.pdf", P, AL)), ["a", "b"])

    def test_variantensuffix(self):
        self.assertEqual(self.ids(tm.resolve("XW-042 TP.pdf", P, AL)), ["e", "f"])

    def test_inhalt_nur_wenn_name_nichts_liefert(self):
        r = tm.resolve("SHM26-008_TP.pdf", P, AL, content="Style SHM26-008 base SNM26-008")
        self.assertEqual((self.ids(r), r[1]), (["d"], "inhalt"))

    def test_kein_treffer_bleibt_offen(self):
        self.assertEqual(tm.resolve("Techpack Dawson Hoodie.pdf", P, AL, content="Dawson")[1], "offen")  # ohne Datei-Alias bleibt offen
        self.assertEqual(tm.resolve("SKM26-099_TP.pdf", P, AL)[1], "offen")   # Regel nur, wenn das Ziel existiert

    def test_kurzer_code_nur_im_namen_und_nur_exakt(self):
        P2 = P + [{"id": "m", "sku": "MP21"}, {"id": "n", "sku": "MP21X"}]
        self.assertEqual(self.ids(tm.resolve("MP21_TP-Unisex zipper Hood.pdf", P2, AL)), ["m"])
        self.assertEqual(tm.resolve("MP22_TP.pdf", P2, AL)[1], "offen")          # keine SKU -> offen
        self.assertEqual(tm.resolve("AB12_TP.pdf", P, AL)[1], "offen")
        self.assertEqual(tm.resolve("SHM26-009_TP.pdf", P2, AL, content="siehe MP21 und AB12")[1], "offen")   # Inhalt: keine kurzen Codes
        self.assertEqual(tm.codes("MP21_TP.pdf"), [])


class LeserFehlt(unittest.TestCase):
    def test_fehlender_pdf_leser_wird_gemeldet(self):
        import builtins
        import tempfile
        real = builtins.__import__

        def fake(name, *a, **k):
            if name == "fitz":
                raise ImportError("kein fitz")
            return real(name, *a, **k)
        tm.LESER_FEHLT.clear()
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "x.pdf"; f.write_bytes(b"%PDF")
            builtins.__import__ = fake
            try:
                self.assertEqual(tm.file_text(f), "")
            finally:
                builtins.__import__ = real
        self.assertIn("PyMuPDF (PDF-Leser)", tm.LESER_FEHLT)
        tm.LESER_FEHLT.clear()


if __name__ == "__main__":
    unittest.main()
