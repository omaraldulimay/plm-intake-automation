import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import vendors_new as vn  # noqa: E402

V = [{"name": "LIEFERANT_V LIMITED", "description": ""}, {"name": "LIEFERANT_AA", "description": "Payee: LIEFERANT_Z COMPANY LIMITED"},
     {"name": "Lieferant A", "description": ""}, {"name": "Lieferant U", "description": ""}]


class Aehnlichkeit(unittest.TestCase):
    def test_alias_verdacht(self):
        self.assertTrue(vn.similar("Lieferant V (Myanmar) Co., Ltd", V))
        self.assertTrue(vn.similar("LIEFERANT_Z COMPANY LIMITED", V))
        self.assertTrue(vn.similar("Lieferant A Exports", V))

    def test_tippfehler_im_firmenkern_und_mail_domain(self):
        v = V + [{"name": "Lieferant I", "description": ""}, {"name": "Lieferant E", "description": ""}]
        self.assertTrue(vn.similar("LIEFERANT_I TEKSTIL SANAYI VE TICARET LIMITED SIRKETI", v))
        spec = {"name": "Voellig Anders Textile", "contacts": [{"email": "kontakt@lieferant-e.example"}]}
        self.assertEqual(vn.create(spec, v)["status"], "ALIAS_VERDACHT")

    def test_wirklich_neu(self):
        self.assertEqual(vn.similar("Lieferant AB Pvt Ltd", V), [])
        self.assertEqual(vn.similar("SPEDITION_B Spedition B Kontor GmbH", V), [])

    def test_create_blockt_bei_alias_und_ohne_apply_nichts(self):
        self.assertEqual(vn.create({"name": "Lieferant A Exports"}, V)["status"], "ALIAS_VERDACHT")
        self.assertEqual(vn.create({"name": "Brand New Textile"}, V)["status"], "TROCKENLAUF")

    def test_bankdaten_in_beschreibung_werden_abgelehnt(self):
        with self.assertRaises(ValueError):
            vn.description({"name": "X", "description_parts": {"note": "IBAN DE89 3704 0044 0532 0130 00"}})

    def test_spec_aus_vendor_info(self):
        s = vn.spec_from_info("SPEDITION_B", {"legal_name": "SPEDITION_B GmbH", "role": "FORWARDER", "contacts": [{"name": "A", "email": "a@x.de"}]})
        self.assertEqual(s["name"], "SPEDITION_B GmbH"); self.assertIn("not a goods supplier", s["description_parts"]["note"]); self.assertEqual(len(s["contacts"]), 1)


if __name__ == "__main__":
    unittest.main()
