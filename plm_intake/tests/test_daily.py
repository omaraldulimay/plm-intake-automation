import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import daily, ledger  # noqa: E402
from plm_intake.tests.test_core import CTX, po  # noqa: E402


def ev_file(mail_id="m9"):
    return {"mail_id": mail_id, "mail_date": "2026-10-12 18:00", "from": "x", "subject": "s", "events": [
        {"type": "SCHEDULE", "vendor": "Lieferant C", "ref": {"po_number": "XW-SM260513"}, "date": "2026-10-15", "summary": "ETD 15.10.", "details": {"new_etd": "2026-10-15"}, "confidence": 0.9, "key": "k" + mail_id}]}


class Taeglich(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(self.tmp.name)
        self.inbox, self.intake = d / "inbox", d / "intake"
        self.inbox.mkdir(); self.intake.mkdir()
        self.ctx = d / "ctx.json"; json.dump(CTX, open(self.ctx, "w"))
        self.addCleanup(self.tmp.cleanup)

    def go(self, *extra):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = daily.main(["--inbox", str(self.inbox), "--ctx", str(self.ctx), "--intake", str(self.intake), *extra])
        return rc, buf.getvalue()

    def put(self, name, obj): json.dump(obj, open(self.inbox / name, "w"))
    def last(self): return json.load(open(self.intake / "last_run.json"))

    def test_neue_datei_wird_bewertet_und_js_erzeugt(self):
        self.put("m1_1.json", po()); rc, out = self.go()
        self.assertEqual(rc, 0); st = self.last(); self.assertEqual(list(st["ready"]), ["m1_1.json"]); self.assertEqual(len(st["js"]), 1)
        self.assertTrue((self.intake / "ready" / "m1_1.json").exists()); self.assertIn("CREATE 1", out)

    def test_commit_merkt_erledigt_und_naechster_lauf_ignoriert_die_datei(self):
        self.put("m1_1.json", po()); self.go(); self.go("--commit")
        led = ledger.load(self.intake / "ledger.json"); self.assertEqual(led["m1_1.json"]["status"], "applied")
        rc, out = self.go(); self.assertEqual(self.last()["ready"], {}); self.assertIn("Neu: 0 Dokument-Dateien", out)

    def test_geaenderte_datei_neue_fassung_ist_wieder_offen(self):
        self.put("m1_1.json", po()); self.go(); created = json.load(open(self.intake / "ready" / "m1_1.json")); self.go("--commit")
        ctx = json.load(open(self.ctx))   # so sieht das PLM nach dem Einspielen aus
        ctx["orders"].append({"id": "NEU", "orderNumber": 50, "title": created["title"], "poNumber": created["poNumber"], "manufacturer": {"id": created["manufacturer"]},
                              "totalCost": created["totalCost"], "totalNumberOfPieces": created["totalNumberOfPieces"]}); json.dump(ctx, open(self.ctx, "w"))
        v2 = po(); v2["items"][0]["variants"][0]["sizes"]["S"] = 11; v2["payments"][1]["amount"] = 290.0; self.put("m1_1.json", v2)
        self.go(); self.assertEqual(self.last()["ready"], {})   # neue Fassung einer bestehenden PO: UPDATE zur Pruefung, nie neu anlegen
        self.assertEqual(json.load(open(self.intake / "blocked" / "m1_1.json"))["decision"], "UPDATE")

    def test_blockierte_dateien_bleiben_offen_und_werden_neu_bewertet(self):
        self.put("m2_1.json", po(vendor="Nirgendwo")); self.go(); self.go("--commit")
        self.assertEqual(ledger.load(self.intake / "ledger.json"), {})
        ctx = json.load(open(self.ctx)); ctx["vendors"].append({"id": "V_N", "name": "Nirgendwo"}); json.dump(ctx, open(self.ctx, "w"))
        self.go(); self.assertEqual(list(self.last()["ready"]), ["m2_1.json"])

    def test_identische_order_wird_als_skip_gemerkt(self):
        ctx = json.load(open(self.ctx)); ctx["orders"][0]["totalCost"] = 18587.0; json.dump(ctx, open(self.ctx, "w"))
        self.put("m3_1.json", po(po_number="XW-SM260513", items=[{"sku": None, "name": "n", "variants": [{"color": "a", "price": 1.0, "sizes": {"S": 18587}}]}],
                                 payments=[{"name": "p", "status": "Unpaid", "amount": 18587.0, "due": "2026-09-22"}]))
        self.go(); self.go("--commit"); self.assertEqual(ledger.load(self.intake / "ledger.json")["m3_1.json"]["status"], "skipped")

    def test_ereignisse_werden_getrennt_behandelt_und_gemerkt(self):
        self.put("m9_events.json", ev_file()); self.go(); st = self.last()
        self.assertEqual(st["events"], ["m9_events.json"]); self.assertTrue(any(j.startswith("events_") for j in st["js"]))
        self.go("--commit"); self.go(); self.assertEqual(self.last()["events"], [])

    def test_nur_voll_zugeordnete_ereignisdateien_werden_als_erledigt_vorgemerkt(self):
        self.put("m9_events.json", ev_file("m9"))
        lose = ev_file("m8"); lose["events"][0]["ref"] = {"po_number": "GIBTSNICHT99"}; lose["events"][0]["key"] = "lose"; self.put("m8_events.json", lose)
        gemischt = ev_file("m7"); gemischt["events"].append(dict(gemischt["events"][0], key="x2", ref={"po_number": "NIRGENDWO1"}, summary="anderes")); self.put("m7_events.json", gemischt)
        self.go(); self.assertEqual(self.last()["events"], ["m9_events.json"])
        self.go("--commit"); led = ledger.load(self.intake / "ledger.json"); self.assertEqual(list(led), ["m9_events.json"])
        self.go(); self.assertEqual(sorted(f.name for f in self.inbox.glob("*_events.json") if f.name not in ledger.load(self.intake / "ledger.json")), ["m7_events.json", "m8_events.json"])

    def test_kaputte_json_datei_stoppt_den_lauf_nicht(self):
        (self.inbox / "kaputt.json").write_text("{nicht json"); self.put("m1_1.json", po()); rc, out = self.go()
        self.assertEqual(rc, 0); self.assertEqual(list(self.last()["ready"]), ["m1_1.json"]); self.assertIn("BLOCK", out)

    def test_leere_inbox_und_fehlender_pfad(self):
        rc, out = self.go(); self.assertEqual(rc, 0); self.assertIn("keine (nichts zu tun)", out)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(daily.main(["--inbox", str(self.inbox / "gibtsnicht"), "--intake", str(self.intake)]), 2)

    def test_pfad_aus_config(self):
        (self.intake / "config.json").write_text(json.dumps({"inbox": str(self.inbox)}))
        self.assertEqual(daily.resolve_inbox(None, self.intake), self.inbox)
        self.assertEqual(daily.resolve_inbox("/x/y", self.intake), Path("/x/y"))

    def test_merkbuch_wird_atomar_geschrieben_und_ueberlebt_leere_datei(self):
        p = self.intake / "ledger.json"; ledger.save(p, {"a": 1}); self.assertEqual(ledger.load(p), {"a": 1}); self.assertFalse(p.with_suffix(".tmp").exists())

    def test_commit_ohne_vorherigen_lauf_ist_harmlos(self):
        rc, out = self.go("--commit"); self.assertEqual(rc, 0); self.assertIn("0 Bestellungen", out)


if __name__ == "__main__":
    unittest.main()
