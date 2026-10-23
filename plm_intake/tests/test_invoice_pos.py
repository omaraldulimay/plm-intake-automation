import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import invoice_pos  # noqa: E402


class OhnePreis(unittest.TestCase):
    def test_bestellung_ohne_preis_wird_klaerfall_statt_inbox_datei(self):
        with tempfile.TemporaryDirectory() as d:
            p2 = Path(d); (p2 / "x" / "extract").mkdir(parents=True)
            for fid, price in (("att_ok", 4.5), ("att_null", None), ("att_zero", 0)):
                doc = {"order": {"currency": "USD", "po_date": "2026-06-25", "items": [{"style": "S1", "color": "black", "sizes": {"M": 10}, "qty": 10, "price": price}]}}
                (p2 / "x" / "extract" / (fid + ".json")).write_text(json.dumps(doc))
            jobs = [("x", "att_ok", "V", "PO-OK", "n"), ("x", "att_null", "V", "PO-NULL", "n"), ("x", "att_zero", "V", "PO-ZERO", "n")]
            with mock.patch.object(invoice_pos, "P2", p2), mock.patch.object(invoice_pos, "OUT", p2 / "B11" / "inbox"), mock.patch.object(invoice_pos, "JOBS", jobs):
                invoice_pos.main()
            self.assertEqual(sorted(f.name for f in (p2 / "B11" / "inbox").glob("*.json")), ["PO-OK.json"])
            txt = (p2 / "B11" / "klaerfaelle_preis.md").read_text()
            self.assertIn("PO-NULL", txt); self.assertIn("PO-ZERO", txt); self.assertNotIn("PO-OK", txt)


if __name__ == "__main__":
    unittest.main()
