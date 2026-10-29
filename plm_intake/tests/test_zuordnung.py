import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import zuordnung  # noqa: E402

O = [{"id": "o1", "title": "A PO", "orderNumber": 57, "createdAt": "2026-03-01T00:00:00Z", "status": "In Production"},
     {"id": "o2", "title": "B PO", "orderNumber": 58, "createdAt": "2026-03-01T00:00:00Z", "status": "Complete"}]


def row(i, mk, zu="", mail="m1", status="offen", rueck=""):
    return {"id": i, "values": {"Quelle": "x | ev:" + mk, "Zuordnung": zu, "Mail-ID": mail, "Status": status, "Rückmeldung": rueck}}



def setUpModule():
    from plm_intake import po_ids
    po_ids.set_registry(None)   # Registry ist global: Tests laufen im alten Format


def tearDownModule():
    from plm_intake import po_ids
    po_ids.set_registry(None)

class Z(unittest.TestCase):
    def test_gruppe_und_nur(self):
        rows = [row("r1", "aaaaaaaa", "PO26-057"), row("r2", "bbbbbbbb"), row("r3", "cccccccc", mail="m2")]
        p = zuordnung.plan(rows, O, {}, {})
        self.assertEqual(p["ev_ov"], {"aaaaaaaa": "o1", "bbbbbbbb": "o1"})
        self.assertEqual(p["angewendet"], 1)
        self.assertIn("angewendet: PO26-057, 2 Ereignisse", p["updates"][0]["rueck"])
        p = zuordnung.plan([row("r1", "aaaaaaaa", "PO26-057 !nur"), row("r2", "bbbbbbbb")], O, {}, {})
        self.assertEqual(p["ev_ov"], {"aaaaaaaa": "o1"})

    def test_info_setzt_erledigt(self):
        p = zuordnung.plan([row("r1", "aaaaaaaa", "Info")], O, {}, {})
        self.assertEqual(p["ev_ov"], {"aaaaaaaa": "__info__"}); self.assertEqual(p["updates"][0]["status"], "erledigt")

    def test_ungueltig(self):
        for val, txt in (("PO26-999", "unbekannt"), ("PO26-058", "abgeschlossen"), ("#99", "unbekannt")):
            p = zuordnung.plan([row("r1", "aaaaaaaa", val)], O, {}, {})
            self.assertEqual(p["ev_ov"], {}); self.assertEqual(p["abgelehnt"], 1)
            self.assertIn(txt, p["updates"][0]["rueck"]); self.assertIsNone(p["updates"][0]["status"])

    def test_konflikt_ueberschreibt_nie(self):
        p = zuordnung.plan([row("r1", "aaaaaaaa", "PO26-057")], O, {"aaaaaaaa": "o2"}, {})
        self.assertEqual(p["ev_ov"], {"aaaaaaaa": "o2"}); self.assertEqual(p["abgelehnt"], 1); self.assertIn("Konflikt", p["updates"][0]["rueck"])
        p = zuordnung.plan([row("r1", "aaaaaaaa", "PO26-057"), row("r2", "bbbbbbbb")], O, {"bbbbbbbb": "__info__"}, {})
        self.assertEqual(p["ev_ov"]["bbbbbbbb"], "__info__"); self.assertIn("1 wegen Konflikt", p["updates"][0]["rueck"])

    def test_limit_und_idempotenz(self):
        rows = [row("r%d" % i, "%08x" % i, "info", mail="m%d" % i) for i in range(40)]
        p = zuordnung.plan(rows, O, {}, {}); self.assertEqual(p["angewendet"], 30); self.assertEqual(p["ungelesen"], 10)
        p = zuordnung.plan([row("r1", "aaaaaaaa", "PO26-057")], O, {"aaaaaaaa": "o1"}, {}); self.assertEqual((p["angewendet"], p["schon"], p["updates"]), (0, 1, []))

    def test_run_trockenlauf_schreibt_nichts(self):
        import tempfile
        calls = []
        def runner(js):
            calls.append(js); return [row("r1", "aaaaaaaa", "info")]
        d = Path(tempfile.mkdtemp())
        r = zuordnung.run(O, d, (), runner=runner, apply=False, cfg={"tableId": "t"})
        self.assertEqual((r["angewendet"], len(calls)), (1, 1)); self.assertFalse((d / "event_overrides.json").exists())
        r = zuordnung.run(O, d, (), runner=lambda js: [row("r1", "aaaaaaaa", "info")] if "READ" in js or "updateCustomRow" not in js else {"written": 1, "verified": 1, "zuordnung_erhalten": 1}, apply=True, backup_dir=d / "bk", cfg={"tableId": "t"})
        self.assertEqual(zuordnung.events.load_event_overrides(d), {"aaaaaaaa": "__info__"}); self.assertEqual(r["fehler"], [])

class JsKonstanten(unittest.TestCase):
    def test_alle_in_main_genutzten_js_texte_existieren(self):
        import re
        from plm_intake import zuordnung
        src = Path(zuordnung.__file__).read_text()
        for name in set(re.findall(r"\b([A-Z_]+_JS)\b", src)):
            self.assertTrue(hasattr(zuordnung, name), name)

class Auswahlliste(unittest.TestCase):
    O = [{"id": "o1", "title": "PO-ALPHA-1", "orderNumber": 57, "createdAt": "2026-07-02T10:00:00Z", "totalNumberOfPieces": 76000, "manufacturer": {"id": "v1", "name": "Lieferant A"}, "status": "In Production"},
         {"id": "o2", "title": "PO-ALPHA-2", "orderNumber": 60, "createdAt": "2026-08-02T10:00:00Z", "manufacturer": {"id": "v1", "name": "Lieferant A"}, "status": "Complete"},
         {"id": "o3", "title": "ZZ-FULLCASE-1", "orderNumber": 61, "createdAt": "2026-08-03T10:00:00Z", "manufacturer": {"id": "v1", "name": "Lieferant A"}, "status": "Draft"}]

    def test_optionen_nur_laufende_ohne_test_und_info_zuerst(self):
        from plm_intake import zuordnung
        o = zuordnung.dropdown_options(self.O)
        self.assertEqual(o[0], "Info")
        self.assertEqual(o[1:], ["Lieferant A · PO26-057 · PO-ALPHA-1 · 76.000 Stk"])

    def test_gewaehlte_option_wird_wie_eine_po_id_aufgeloest(self):
        from plm_intake import zuordnung
        order, err = zuordnung.resolve_order("Lieferant A · PO26-057 · PO-ALPHA-1 · 76.000 Stk", self.O)
        self.assertIsNone(err); self.assertEqual(order["id"], "o1")
        self.assertEqual(zuordnung.parse("Info")[0], "info")

    def test_sync_ruft_den_browser_mit_den_optionen(self):
        from plm_intake import zuordnung
        seen = []
        zuordnung.sync_dropdown(self.O, runner=lambda js: seen.append(js) or {}, apply=False, cfg={"tableId": "t1"})
        self.assertIn("Lieferant A", seen[0]); self.assertIn('"apply": false', seen[0])


if __name__ == "__main__":
    unittest.main()
