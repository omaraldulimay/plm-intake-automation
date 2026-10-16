import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plm_intake import run, verify, core  # noqa: E402
from plm_intake.tests.test_core import CTX, TODAY, po  # noqa: E402


class Lauf(unittest.TestCase):
    def test_doppelt_in_derselben_inbox_nur_einmal_create(self):
        res = run.process([("a.json", po()), ("b.json", po())], CTX, TODAY)
        self.assertEqual([r.decision for _, r in res], ["CREATE", "SKIP"])

    def test_gleiche_nummer_zwei_fassungen_zweite_ist_update(self):
        v2 = po()
        v2["items"][0]["variants"][0]["sizes"]["S"] = 11
        v2["payments"][1]["amount"] = 290.0
        res = run.process([("a.json", po()), ("b.json", v2)], CTX, TODAY)
        self.assertEqual([r.decision for _, r in res], ["CREATE", "UPDATE"])

    def test_kaputte_eingabe_stoppt_den_lauf_nicht(self):
        res = run.process([("kaputt.json", {"_unreadable": "x"}), ("gut.json", po())], CTX, TODAY)
        self.assertEqual(res[0][1].decision, "BLOCK")
        self.assertEqual(res[1][1].decision, "CREATE")

    def test_kaputte_struktur_exception_wird_gefangen(self):
        res = run.process([("x.json", {"vendor": "LIEFERANT_AA", "po_number": "1", "currency": "USD", "items": "kein array"})], CTX, TODAY)
        self.assertEqual(res[0][1].decision, "BLOCK")

    def test_kontext_wird_nicht_veraendert(self):
        before = copy.deepcopy(CTX)
        run.process([("a.json", po())], CTX, TODAY)
        self.assertEqual(CTX, before)

    def test_bericht_enthaelt_zusammenfassung(self):
        rep = run.render_report(run.process([("a.json", po()), ("b.json", po(vendor="Nirgendwo"))], CTX, TODAY))
        self.assertIn("CREATE 1", rep)
        self.assertIn("BLOCK 1", rep)


class Verzeichnisse(unittest.TestCase):
    def test_ereignis_dateien_werden_vom_po_lauf_ignoriert_und_vom_ereignis_lauf_verarbeitet(self):
        import tempfile
        from plm_intake import events_run
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d / "inbox").mkdir(); out = d / "out"
            json.dump(po(), open(d / "inbox" / "m1_1.json", "w"))
            json.dump({"mail_id": "m2", "mail_date": "2026-10-12 18:00", "from": "x", "subject": "s", "events": [
                {"type": "SCHEDULE", "vendor": "Lieferant C", "ref": {"po_number": "XW-SM260513"}, "date": "2026-10-15", "summary": "ETD 15.10.", "details": {"new_etd": "2026-10-15"}, "confidence": 0.9, "key": "k"}]},
                open(d / "inbox" / "m2_events.json", "w"))
            ctx = d / "ctx.json"; json.dump(dict(CTX, aliases={}), open(ctx, "w"))
            # PO-Lauf: nur m1_1 (kein Fehler wegen events-Datei)
            res_files = sorted(f.name for f in (d / "inbox").glob("*.json") if not f.name.endswith("_events.json"))
            self.assertEqual(res_files, ["m1_1.json"])
            events_run.main(["--inbox", str(d / "inbox"), "--ctx", str(ctx), "--out", str(out)])
            self.assertTrue((out / "events_report.md").exists()); self.assertEqual(len(list(out.glob("events_*.js"))), 1)
            self.assertIn("PO-XW-SM260513", (out / "events_report.md").read_text())
            self.assertIn("ETD 15.10.", next(out.glob("events_*.js")).read_text())


class Nachpruefung(unittest.TestCase):
    def live_from(self, payload, n=1):
        o = {"id": "L", "orderNumber": 99, "title": payload["title"], "poNumber": payload["poNumber"], "manufacturer": {"id": payload["manufacturer"]},
             "totalCost": payload["totalCost"], "totalNumberOfPieces": payload["totalNumberOfPieces"], "items": copy.deepcopy(payload["items"]),
             "payments": copy.deepcopy(payload["payments"])}
        return [copy.deepcopy(o) for _ in range(n)]

    def setUp(self):
        self.p = core.build(po(), CTX, TODAY).payload

    def test_ok(self): self.assertEqual(verify.check([self.p], self.live_from(self.p)), [])
    def test_fehlt(self): self.assertTrue(any("FEHLT" in b for b in verify.check([self.p], [])))
    def test_doppelt(self): self.assertTrue(any("DOPPELT" in b for b in verify.check([self.p], self.live_from(self.p, 2))))

    def test_abweichungen(self):
        live = self.live_from(self.p)
        live[0]["totalCost"] = 1.0
        live[0]["items"][0]["variants"][0]["amounts"][0]["quantity"] += 1
        live[0]["items"][0].pop("product")
        live[0]["payments"][0]["amount"] += 5
        bad = " | ".join(verify.check([self.p], live))
        for k in ("SUMME", "MENGE_IN_POSITIONEN", "PRODUKTLINK", "ZAHLUNGEN"):
            self.assertIn(k, bad)


@unittest.skipUnless(shutil.which("node"), "node fehlt")
class BrowserSkript(unittest.TestCase):
    def run_js(self, payloads, create_impl, dry=False):
        js = run.make_js(payloads, dry)
        harness = "globalThis.window = {}; %s\nconst f = async () => (%s);\nf().then(r => console.log(JSON.stringify(r)));" % (create_impl, js)
        out = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def pl(self, t):
        p = copy.deepcopy(core.build(po(), CTX, TODAY).payload)
        p["title"] = t
        return p

    OK = "let n=100; window.__createOrder = async p => ({errors: [], data: {createOrder: {orderNumber: ++n, totalCost: p.totalCost, totalNumberOfPieces: p.totalNumberOfPieces}}});"

    def test_alle_ok(self):
        r = self.run_js([self.pl("A"), self.pl("B")], self.OK)
        self.assertEqual([x["orderNumber"] for x in r], [101, 102])

    def test_abbruch_beim_ersten_fehler_kein_weitermachen(self):
        impl = "let c=0; window.__createOrder = async p => (++c===2 ? {errors:['boom'], data:null} : {errors:[], data:{createOrder:{orderNumber:c,totalCost:1,totalNumberOfPieces:1}}});"
        r = self.run_js([self.pl("A"), self.pl("B"), self.pl("C")], impl)
        self.assertEqual(len(r), 2)
        self.assertTrue(r[1]["unsure"])

    def test_exception_bricht_ab(self):
        r = self.run_js([self.pl("A"), self.pl("B")], "window.__createOrder = async p => { throw new Error('netz weg'); };")
        self.assertEqual(len(r), 1)
        self.assertIn("netz weg", r[0]["error"])

    def test_helfer_nicht_geladen(self):
        r = self.run_js([self.pl("A")], "")
        self.assertIn("Helfer nicht geladen", r[0]["fatal"])

    def test_doppelter_titel_im_lauf_wird_uebersprungen(self):
        r = self.run_js([self.pl("A"), self.pl("A")], self.OK)
        self.assertEqual([("skipped" in x) for x in r], [False, True])

    def test_trockenlauf_ruft_createorder_nie_auf(self):
        r = self.run_js([self.pl("A")], "window.__createOrder = async p => { throw new Error('darf nicht'); };", dry=True)
        self.assertTrue(r[0]["dry"])

    def test_payload_wird_unveraendert_uebergeben(self):
        p = self.pl("A")
        p["notes"] = "Umlaute äöü \"Anfuehrungszeichen\" </script> `backtick` ${x}"
        impl = "window.__createOrder = async q => ({errors:[], data:{createOrder:{orderNumber:1,totalCost:0,totalNumberOfPieces:0,echo:q.notes}}});"
        js = run.make_js([p])
        harness = "globalThis.window={}; %s\nlet got; const orig=window.__createOrder; window.__createOrder=async q=>{got=q.notes; return orig(q)};\n(%s).then(()=>console.log(JSON.stringify(got)))" % (impl, js)
        out = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=30)
        self.assertEqual(json.loads(out.stdout.strip()), p["notes"])


if __name__ == "__main__":
    unittest.main()
