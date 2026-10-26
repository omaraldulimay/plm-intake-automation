import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import klaerfaelle  # noqa: E402

V = [{"id": "v1", "name": "Lieferant C", "contacts": [{"email": "kontakt@lieferant-c.example"}]}]


def u(type_="SHIPMENT", vendor=None, po=None, style=None, reason="keine Order gefunden", frm="kontakt@firma.example", summary="Container verladen", key="k1"):
    return {"event": {"type": type_, "vendor": vendor, "ref": {"po_number": po, "style": style, "container": None}, "date": "2026-10-12", "summary": summary, "key": key,
                      "_mail": {"id": "m1", "date": "2026-10-12 10:00", "from": frm, "subject": "Re: XW-042"}}, "reason": reason}


class NeueSpalten(unittest.TestCase):
    def test_werte(self):
        x = u(vendor="Lieferant C", po="PO-1", style="XW-042", reason="mehrdeutig: PO-A, PO-B", frm='"Nicole" <kontakt@lieferant-c.example>')
        x["event"]["action_needed"] = "Termin bestaetigen"
        x["event"]["source_quote"] = "Q " * 400
        r = klaerfaelle.select([x], V, None, None, {"m1": "Datei mails_2026-10-12_100000_1.txt"})[0]["values"]
        self.assertEqual(r["Nummer"], "PO-1 / XW-042")
        self.assertEqual(r["Mögliche PO"], "PO-A, PO-B")
        self.assertEqual(r["Aktion"], "Termin bestaetigen")
        self.assertLessEqual(len(r["Zitat"]), 300)
        self.assertEqual(r["Mail-ID"], "m1")
        self.assertEqual(r["Betreff"], "Re: XW-042")
        self.assertTrue(r["Suche"].startswith("m1 | PLM-Mails/Datei mails_2026-10-12_1000"))
        self.assertIn("from:kontakt@lieferant-c.example after:2026/10/11 before:2026/10/14", r["Suche"])

    def test_ohne_kandidaten_und_bankdaten(self):
        x = u(vendor="Lieferant C", reason="mehrdeutig: 3 laufende Orders von X")
        x["event"]["source_quote"] = "IBAN DE89 3704 0044 0532 0130 00 bitte"
        r = klaerfaelle.select([x], V)[0]["values"]
        self.assertEqual(r["Mögliche PO"], "")
        self.assertNotIn("3704", r["Zitat"])

    def test_sync_js_fuellt_nur_leere(self):
        js = klaerfaelle.SYNC_JS
        self.assertIn("P.fill", js)
        self.assertIn("cur[k] === ''", js)
        self.assertNotIn("Status: P", js)


class Auswahl(unittest.TestCase):
    def test_echter_fall_mit_lieferant(self):
        r = klaerfaelle.select([u(vendor="LIEFERANT_C CO.,LTD.", style="XW-042", reason="mehrdeutig: PO-XW-SM260730, PO-XW042-20260709")], V)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["category"], "Lieferant C")
        self.assertEqual(r[0]["values"]["Art"], "Versand")
        self.assertTrue(r[0]["values"]["Warum offen"].startswith("passt zu mehreren"))
        self.assertIn("ev:" + r[0]["marker"], r[0]["values"]["Quelle"])
        self.assertEqual(r[0]["values"]["Status"], "offen")

    def test_info_muster_und_fremdes_fliegen_raus(self):
        rows = klaerfaelle.select([u(type_="SAMPLE", vendor="Lieferant C"), u(reason="info: Dienstleister (UPS) ohne Bestellbezug", key="k2"),
                                   u(type_="PAYMENT", vendor="Anthropic, PBC", summary="Claude Pro 18 EUR", key="k3")], V)
        self.assertEqual(rows, [])

    def test_lieferant_ueber_domain_und_ohne_lieferant_mit_nummer(self):
        from plm_intake import events
        dom = events.domain_vendors(V)
        r = klaerfaelle.select([u(frm="Nicole <kontakt@lieferant-c.example>", key="a"), u(po="26M10_001", key="b")], V, None, dom)
        self.assertEqual([x["category"] for x in r], ["Lieferant C", klaerfaelle.OHNE])

    def test_keine_doppelten_marker(self):
        self.assertEqual(len(klaerfaelle.select([u(vendor="Lieferant C"), u(vendor="Lieferant C")], V)), 1)


if __name__ == "__main__":
    unittest.main()


class Loeschen(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.bk = self.tmp / "b.json"
        self.cfg = {"tableId": "T"}

    def cand(self, i, marker="abcdef01"):
        return {"id": "r%d" % i, "marker": marker, "category": "X", "values": {"Datum": "2026-10-01", "Art": "Versand", "Was": "w", "Status": "erledigt"}}

    def test_js_loescht_nicht_ohne_sicherung_und_nicht_im_sync(self):
        self.assertNotIn("deleteCustomRow", klaerfaelle.SYNC_JS)
        self.assertNotIn("Status: 'erledigt' }", klaerfaelle.SYNC_JS)
        self.assertIn("deleteCustomRow", klaerfaelle.DELETE_JS)
        self.assertIn("resolved.has(it.marker)", klaerfaelle.DELETE_JS)

    def test_sicherung_vor_loeschen_und_felder(self):
        calls = []

        def runner(js):
            calls.append(js)
            self.assertTrue(self.bk.exists())   # Sicherung steht schon
            return {"deleted": 1, "rows_total": 5, "open_total": 4, "errors": []}
        r = klaerfaelle.delete_solved([self.cand(1)], {"abcdef01"}, self.cfg, runner, {"abcdef01": "PO-1"}, "lauf1", self.bk)
        self.assertEqual(r["deleted"], 1)
        e = json.loads(self.bk.read_text())[0]
        self.assertEqual((e["Marker"], e["Datum"], e["Art"], e["Text"], e["Order"], e["Lauf"]), ("abcdef01", "2026-10-01", "Versand", "w", "PO-1", "lauf1"))
        self.assertIn("geloest am", e)

    def test_limit_50_und_rest(self):
        n = []
        r = klaerfaelle.delete_solved([self.cand(i, "%08x" % i) for i in range(60)], set(), self.cfg, lambda js: n.append(js) or {"deleted": 50, "errors": []}, {}, "l", self.bk)
        self.assertEqual(r["pending"], 10)
        self.assertEqual(len(json.loads(self.bk.read_text())), 50)
        self.assertEqual(json.loads(n[0].split("const P = ")[1].split(";\n")[0])["items"].__len__(), 50)

    def test_trockenlauf_loescht_nichts(self):
        r = klaerfaelle.delete_solved([self.cand(1)], set(), self.cfg, lambda js: self.fail("Lauf"), {}, "l", self.bk, dry=True)
        self.assertEqual(r["would_delete"], 1)
        self.assertFalse(self.bk.exists())

    def test_ohne_marker_nie(self):
        c = self.cand(1); c["marker"] = None
        r = klaerfaelle.delete_solved([c], set(), self.cfg, lambda js: self.fail("Lauf"), {}, "l", self.bk)
        self.assertEqual(r["deleted"], 0)

    def test_sicherung_scheitert_kein_loeschen(self):
        orig = klaerfaelle.save_backup
        klaerfaelle.save_backup = lambda *a, **k: False
        try:
            r = klaerfaelle.delete_solved([self.cand(1)], set(), self.cfg, lambda js: self.fail("Lauf"), {}, "l", self.bk)
        finally:
            klaerfaelle.save_backup = orig
        self.assertTrue(r["errors"])

    def test_state_file(self):
        from plm_intake import cloud
        self.assertIn("intake/klaerfaelle_erledigt.json", cloud.STATE_FILES)
