import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import portal_abgleich as pa  # noqa: E402


class Abgleich(unittest.TestCase):
    def test_lieferant_auch_bei_tippfehler(self):
        vk = pa.core("LIEFERANT_I TEKSTİL SANAYİ VE TİC. LTD. ŞTİ.")
        self.assertTrue(pa.vendor_ok(vk, "Lieferant I; Yenibosna Merkez Mahallesi"))
        self.assertFalse(pa.vendor_ok(vk, "Lieferant J; Taner Emre"))

    def test_zeilen_und_groessen(self):
        po = {"items": [{"sku": "26779", "variants": [{"color": "SCHWARZ", "sizes": {"M": 1910, "2XL": 54}}]}]}
        dl = pa.doc_lines(po)
        self.assertEqual(dl[("26779", "schwarz", "M")], 1910)
        self.assertEqual(dl[("26779", "schwarz", "XXL")], 54)   # 2XL = XXL wie im Portal
        self.assertEqual(pa.collapse(dl)[("26779", "M")], 1910)

    def test_attribute_und_artikelbasis(self):
        self.assertEqual(pa.parse_attr("Color:Schwarz, Size:XS"), ("Schwarz", "XS"))
        self.assertEqual(pa.base("26779-A3"), "26779")


if __name__ == "__main__":
    unittest.main()
