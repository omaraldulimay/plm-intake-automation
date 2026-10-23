import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import events, tagesbericht as tb, vendor_ids as vi  # noqa: E402

V = lambda i, n: {"id": i, "name": n}
VENDORS = [V("a", "Lieferant A"), V("w", "LIEFERANT_AA"), V("x", "Lieferant C"), V("s", "Lieferant I"), V("sa", "Lieferant AE Co. Ltd"),
           V("sy", "Jiangsu Lieferant Extra Handsome co. Ltd"), V("si", "Lieferant E"), V("se", "SEAMTECH / ROOFTECH"), V("z", "ZZ-FULLCASE Vendor"), V("d", "Default Vendor"), V("n", "Neuer Lieferant")]


class VendorIds(unittest.TestCase):
    def test_eindeutig_und_mehrdeutig(self):
        r = vi.assign(["ALP", "LIEFERANT_AA", "LFC", "SPT", "SNT", "SNY", "SMT", "ZZZ", "ALP"], VENDORS)
        z = {c: n for c, n in r["zugeordnet"].values()}
        self.assertEqual(z["ALP"], "Lieferant A"); self.assertEqual(z["LIEFERANT_AA"], "LIEFERANT_AA"); self.assertEqual(z["LFC"], "Lieferant C"); self.assertEqual(z["SPT"], "Lieferant I")
        self.assertEqual(z["SNY"], "Jiangsu Lieferant Extra Handsome co. Ltd"); self.assertEqual(z["SNT"], "Lieferant AE Co. Ltd")
        self.assertNotIn("SMT", z)                                    # Lieferant E oder Seamtech: kein Raten
        self.assertEqual(r["mehrdeutig"][0][0], "SMT"); self.assertEqual(sorted(r["mehrdeutig"][0][1]), ["SEAMTECH / ROOFTECH", "Lieferant E"])
        self.assertEqual(r["ohne_vendor"], ["ZZZ"]); self.assertEqual(r["doppelt"], ["ALP"])
        names = [v["name"] for v in r["ohne_kuerzel"]]
        self.assertIn("Neuer Lieferant", names); self.assertNotIn("Default Vendor", names); self.assertNotIn("ZZ-FULLCASE Vendor", names)

    def test_hoechstens_ein_kuerzel_je_lieferant(self):
        r = vi.assign(["SHK", "SSK"], [V("so", "LIEFERANT_AH")])          # beide passen, keines eindeutig
        self.assertEqual(r["zugeordnet"], {}); self.assertEqual(len(r["mehrdeutig"]), 2)

    def test_signal_nur_token(self):
        self.assertEqual(vi.signal_for_text("PO26-036-ALP Packing list", ["ALP", "LIEFERANT_AA"]), ["ALP"])
        self.assertEqual(vi.signal_for_text("Lieferant A, SALPE", ["ALP"]), [])
        self.assertEqual(vi.vendor_hint("Re: ALP shipment", VENDORS, {"a": "ALP", "w": "LIEFERANT_AA"}), {"a": "ALP"})

    def test_hinweis_neue_lieferanten(self):
        w = vi.warnings_no_id(VENDORS, {"a": "ALP"})
        self.assertTrue(any("Neuer Lieferant" in x for x in w)); self.assertFalse(any("Default" in x or "ZZ-" in x for x in w))
        self.assertEqual(vi.warnings_no_id(VENDORS, {}), [])           # ohne Karte kein Alarm
        self.assertNotEqual(tb.warn_key(w[0]), tb.warn_key(w[1]))      # je Lieferant eigener Schluessel

    def test_plan_ueberschreibt_nie(self):
        res = {"zugeordnet": {"a": ("ALP", "Alpha"), "w": ("LIEFERANT_AA", "LIEFERANT_AA"), "x": ("LFC", "X")}}
        todo, ok, wrong = vi.plan(res, {"a": {"v": None}, "w": {"v": "LIEFERANT_AA"}, "x": {"v": "ABC"}})
        self.assertEqual(todo, [("a", "ALP")]); self.assertEqual(ok, 1); self.assertEqual(wrong, [("x", "LFC", "ABC")])

    def test_kuerzel_ordnet_nie_eine_order_zu_nur_lieferant(self):
        e = {"subject": "PO26-999-ALP packing list", "_mail": {"from": "x@unknown.example", "subject": "ALP"}}
        with mock.patch.object(vi, "load_id_map", return_value={"a": "ALP"}):
            self.assertEqual(events.vendor_of(e, VENDORS)["id"], "a")
            e2 = {"subject": "ALP und LIEFERANT_AA", "_mail": {"from": "x@unknown.example"}}
            with mock.patch.object(vi, "load_id_map", return_value={"a": "ALP", "w": "LIEFERANT_AA"}):
                self.assertIsNone(events.vendor_of(e2, VENDORS))        # zwei Kuerzel -> kein Signal

    def test_zustandsdatei_vorrang_und_fallback(self):
        from plm_intake import cloud
        self.assertIn("intake/lieferanten_ids.json", cloud.STATE_FILES)
        with tempfile.TemporaryDirectory() as d:
            st, old = Path(d) / "st.json", Path(d) / "old" / "lieferanten_ids.json"
            old.parent.mkdir()
            mk = lambda c: json.dumps({"zugeordnet": {"a": {"code": c, "name": "x"}}})
            with mock.patch.object(vi, "STATE_PATH", st), mock.patch.object(vi, "OUTDIR", old.parent):
                self.assertEqual(vi.load_id_map(), {})
                old.write_text(mk("OLD")); self.assertEqual(vi.load_id_map(), {"a": "OLD"})
                st.write_text(mk("NEW")); self.assertEqual(vi.load_id_map(), {"a": "NEW"})

    def test_load_id_map(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"; p.write_text(json.dumps({"zugeordnet": {"a": {"code": "ALP", "name": "A"}}}))
            self.assertEqual(vi.load_id_map(p), {"a": "ALP"}); self.assertEqual(vi.load_id_map(Path(d) / "fehlt.json"), {})


if __name__ == "__main__":
    unittest.main()
