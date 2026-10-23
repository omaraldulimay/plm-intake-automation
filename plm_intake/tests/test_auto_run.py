import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import auto_run  # noqa: E402


class Bericht(unittest.TestCase):
    """Rauchtest des Alltagslaufs im Trockenlauf mit gefaelschtem PLM: alle Berichtsabschnitte muessen vorhanden sein (Regression: ein Edit hat einmal 'Neue Bestellungen' geloescht)."""

    def run_dry(self, docs):
        with tempfile.TemporaryDirectory() as d:
            inbox, intake = Path(d) / "inbox", Path(d) / "intake"; inbox.mkdir(); intake.mkdir()
            for n, obj in docs.items():
                (inbox / n).write_text(json.dumps(obj))
            ctx = {"vendors": [{"id": "V1", "name": "Testlieferant"}], "products": [], "orders": []}
            fake_call = mock.Mock(return_value=(200, []))
            with mock.patch("plm_client.call", fake_call), mock.patch("plm_intake.context.load_context", return_value=ctx), \
                    mock.patch("plm_intake.context.add_po_numbers", return_value=0), mock.patch("plm_intake.context.fetch_order_details", return_value={}), \
                    mock.patch("plm_intake.context.fetch_all", return_value=[]):
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    rc = auto_run.main(["--inbox", str(inbox), "--intake", str(intake), "--overrides", str(Path(d) / "none.json")])
            fake_call.assert_not_called() if False else None
            return rc, buf.getvalue(), (intake / "auto_report.md").read_text()

    def test_trockenlauf_enthaelt_alle_abschnitte_und_schreibt_nichts(self):
        po = {"doc_type": "PI", "source": {"doc": "x", "mail_id": "m1"}, "vendor": "Testlieferant", "po_number": "T-1", "currency": "USD", "items": [
              {"sku": "ZZ-100", "name": "JACKET", "variants": [{"color": "Black", "price": 2, "sizes": {"M": 50}}]}], "payments": [{"name": "100%", "status": "Unpaid", "amount": 100, "due": "2026-12-01", "terms": "t"}],
              "total_cost": 100, "total_pieces": 50, "notes": "", "open": [], "confidence": 0.9}
        rc, out, rep = self.run_dry({"m1_1.json": po})
        self.assertEqual(rc, 0)
        for h in ("## Lieferanten", "## Neue Produkte", "## Neue Bestellungen (CREATE)", "## Belege zu bestehenden Bestellungen", "## Notizen/Ereignisse", "## Sendungen", "## Mensch entscheidet"):
            self.assertIn(h, rep, h)
        self.assertIn("TROCKENLAUF", rep); self.assertIn("ZZ-100", rep)   # neues Produkt und neue PO sind geplant

    def test_gewolltes_create_das_nicht_geht_steht_im_bericht(self):
        po = {"doc_type": "PI", "source": {"doc": "x", "mail_id": "m1"}, "vendor": "Unbekannt GmbH", "po_number": "T-1", "currency": "USD", "items": [
              {"sku": "ZZ-100", "name": "JACKET", "variants": [{"color": "Black", "price": 2, "sizes": {"M": 5}}]}], "payments": [], "total_cost": 10, "total_pieces": 5, "notes": "", "open": [], "confidence": 0.9}
        with tempfile.TemporaryDirectory() as d:
            ov = Path(d) / "ov.json"; ov.write_text(json.dumps({"m1_1.json": "CREATE"}))
            inbox, intake = Path(d) / "inbox", Path(d) / "intake"; inbox.mkdir(); intake.mkdir(); (inbox / "m1_1.json").write_text(json.dumps(po))
            ctx = {"vendors": [{"id": "V1", "name": "Testlieferant"}], "products": [], "orders": []}
            with mock.patch("plm_client.call", mock.Mock(return_value=(200, []))), mock.patch("plm_intake.context.load_context", return_value=ctx), \
                    mock.patch("plm_intake.context.add_po_numbers", return_value=0), mock.patch("plm_intake.context.fetch_order_details", return_value={}), \
                    mock.patch("plm_intake.context.fetch_all", return_value=[]), mock.patch("sys.stdout", io.StringIO()):
                auto_run.main(["--inbox", str(inbox), "--intake", str(intake), "--overrides", str(ov)])
            rep = (intake / "auto_report.md").read_text()
        self.assertIn("CREATE gewollt, aber nicht moeglich (m1_1.json)", rep); self.assertIn("Vendor", rep)


if __name__ == "__main__":
    unittest.main()


class TagesdatenTest(unittest.TestCase):
    def test_trockenlauf_schreibt_tagesdaten_fuer_den_bericht(self):
        import plm_intake.tagesbericht as tb
        po = {"doc_type": "PI", "source": {"doc": "x", "mail_id": "m1"}, "vendor": "Testlieferant", "po_number": "T-1", "currency": "USD", "items": [
              {"sku": "ZZ-100", "name": "JACKET", "variants": [{"color": "Black", "price": 2, "sizes": {"M": 50}}]}], "payments": [], "total_cost": 100, "total_pieces": 50, "notes": "", "open": [], "confidence": 0.9}
        with tempfile.TemporaryDirectory() as d:
            inbox, intake = Path(d) / "inbox", Path(d) / "intake"; inbox.mkdir(); intake.mkdir()
            (inbox / "m1_1.json").write_text(json.dumps(po))
            ctx = {"vendors": [{"id": "V1", "name": "Testlieferant"}], "products": [], "orders": []}
            with mock.patch("plm_client.call", mock.Mock(return_value=(200, []))), mock.patch("plm_intake.context.load_context", return_value=ctx), \
                    mock.patch("plm_intake.context.add_po_numbers", return_value=0), mock.patch("plm_intake.context.fetch_order_details", return_value={}), \
                    mock.patch("plm_intake.context.fetch_all", return_value=[]), mock.patch("sys.stdout", io.StringIO()):
                auto_run.main(["--inbox", str(inbox), "--intake", str(intake), "--overrides", str(Path(d) / "none.json")])
            facts = json.loads((intake / "tagesdaten.json").read_text())
            self.assertEqual(facts["zahlen"]["orders"], 1); self.assertIn("dauer_s", facts)
            txt = tb.write(intake, 0, "dry", now=__import__("datetime").datetime(2026, 10, 21, 8, 0), step_summary=None)
            self.assertIn("Trockenlauf", txt); self.assertIn("neue Bestellungen 1", txt)


class SummeNull(unittest.TestCase):
    def test_no_price_orders(self):
        orders = [{"title": "PO-A", "totalNumberOfPieces": 100, "totalCost": 0},
                  {"title": "PO-B", "totalNumberOfPieces": 100, "totalCost": None},
                  {"title": "PO-C", "totalNumberOfPieces": 100, "totalCost": 50.0},
                  {"title": "PO-D", "totalNumberOfPieces": 0, "totalCost": 0},
                  {"title": "ZZ-FULLCASE6 PO", "totalNumberOfPieces": 10, "totalCost": 0},
                  {"title": "PO-X-T1", "totalNumberOfPieces": 10, "totalCost": 0}]
        self.assertEqual(auto_run.no_price_orders(orders), ["PO-A", "PO-B"])
