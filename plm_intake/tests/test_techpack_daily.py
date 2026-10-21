import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import techpack_daily as td  # noqa: E402

PRODS = [{"id": "p1", "sku": "XW26-006"}, {"id": "p2", "sku": "XW26-007"}]
SINCE = "2026-10-01T00:00:00+00:00"


def f(name, mtime="2026-10-10T00:00:00+00:00", size=100, data=b"x"):
    return {"name": name, "mtime": mtime, "size": size, "get": lambda: data}


class Daily(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "techpack_daily.json"

    def start(self, since=SINCE):
        if since:
            td.save_state(self.state, {"since": since, "done": []})

    def run_(self, files, apply, existing=None, uploader=None):
        up = uploader or mock.Mock(return_value=(True, ""))
        rd = mock.Mock(side_effect=lambda pids: {p: list((existing or {}).get(p, [])) for p in pids})
        lines, res = td.run(PRODS, self.state, apply=apply, source=lambda s: files, reader=rd, uploader=up, aliases={}, text_of=lambda p: "")
        return lines, res, up

    def test_erkennung_dateiname(self):
        self.assertTrue(td.is_techpack_name("2026-10-01_0123456789abcdef_XW26-006_TP.pdf"))
        self.assertFalse(td.is_techpack_name("Size Spec XW26-006.xlsx"))   # Specs werden nicht angehaengt
        self.assertTrue(td.is_techpack_name("BOM XW26-006.xlsx"))
        self.assertFalse(td.is_techpack_name("Invoice_123.pdf"))
        self.assertFalse(td.is_techpack_name("XW26-006_TP.png"))

    def test_neu_seit_merker(self):
        st = {"since": SINCE, "done": ["B_TP.pdf"]}
        files = [f("A_TP.pdf", "2026-09-01T00:00:00+00:00"), f("B_TP.pdf"), f("C_TP.pdf"), f("Rechnung.pdf")]
        self.assertEqual([x["name"] for x in td.find_new(files, st)], ["C_TP.pdf"])
        self.assertEqual(td.find_new(files, {"since": None, "done": []}), [])

    def test_erstlauf_setzt_nur_merker_im_echtlauf(self):
        lines, res, up = self.run_([f("XW26-006_TP.pdf")], apply=False)
        self.assertFalse(self.state.exists()); up.assert_not_called()
        lines, res, up = self.run_([f("XW26-006_TP.pdf")], apply=True)
        self.assertTrue(td.load_state(self.state)["since"]); up.assert_not_called()

    def test_ueberspringen_bei_vorhandener_datei(self):
        self.start()
        ex = {"p1": [{"name": "XW26-006_TP", "fileUrl": "uploads/abc.pdf"}]}
        lines, res, up = self.run_([f("XW26-006_TP.pdf")], apply=True, existing=ex)
        up.assert_not_called(); self.assertEqual(res["vorhanden"], 1)
        # Drive-Link zaehlt nicht als vorhanden
        self.start()   # Merker/done zuruecksetzen
        ex = {"p1": [{"name": "XW26-006_TP", "fileUrl": "https://drive.google.com/x"}]}
        lines, res, up = self.run_([f("XW26-006_TP.pdf")], apply=True, existing=ex)
        up.assert_called_once()

    def test_limit_30(self):
        self.start()
        prods = [{"id": "q%d" % i, "sku": "XW26-%03d" % (100 + i)} for i in range(40)]
        files = [f("XW26-%03d_TP.pdf" % (100 + i), "2026-10-10T00:%02d:00+00:00" % i) for i in range(40)]
        up = mock.Mock(return_value=(True, ""))
        rd = mock.Mock(side_effect=lambda pids: {p: [] for p in pids})
        lines, res = td.run(prods, self.state, apply=True, source=lambda s: files, reader=rd, uploader=up, aliases={}, text_of=lambda p: "")
        self.assertEqual(up.call_count, 30); self.assertEqual(res["rest"], 10)
        st = td.load_state(self.state)
        self.assertEqual(st["since"], SINCE)   # Merker bleibt, Rest kommt naechstes Mal
        self.assertEqual(len(st["done"]), 30)

    def test_gleicher_name_nur_neueste_fassung(self):
        self.start()
        files = [f("2026-10-02_0123456789abcdef_XW26-006_TP.pdf", "2026-10-02T00:00:00+00:00"), f("2026-10-05_fedcba9876543210_XW26-006_TP.pdf", "2026-10-05T00:00:00+00:00")]
        lines, res, up = self.run_(files, apply=True)
        up.assert_called_once()

    def test_spec_wird_nicht_angehaengt(self):
        self.start()
        lines, res, up = self.run_([f("Size Spec XW26-006.xlsx"), f("XW26-006_Grading.xlsx")], apply=True)
        up.assert_not_called(); self.assertEqual(res["neu"], 0)

    def test_nur_neueste_fassung_mit_datum_version(self):
        self.start()
        files = [f("XW26-006_TP_2026-10-02.pdf", "2026-10-02T00:00:00+00:00"), f("XW26-006_TP_v2.pdf", "2026-10-05T00:00:00+00:00"), f("XW26-006_TP_BOM.pdf", "2026-10-03T00:00:00+00:00")]
        lines, res, up = self.run_(files, apply=True)
        self.assertEqual(sorted(c.args[1] for c in up.call_args_list), ["XW26-006_TP_BOM.pdf", "XW26-006_TP_v2.pdf"])

    def test_trockenlauf_ruft_keinen_upload_auf(self):
        self.start()
        lines, res, up = self.run_([f("XW26-006_TP.pdf")], apply=False)
        up.assert_not_called(); self.assertTrue(any("wuerde hochladen" in l for l in lines))
        self.assertEqual(td.load_state(self.state), {"since": SINCE, "done": []})   # Merker unveraendert

    def test_ohne_produkt_im_bericht(self):
        self.start()
        lines, res, up = self.run_([f("ZZZ99_TP.pdf")], apply=False)
        self.assertIn("### Techpacks ohne Produkt", lines); up.assert_not_called()


if __name__ == "__main__":
    unittest.main()
