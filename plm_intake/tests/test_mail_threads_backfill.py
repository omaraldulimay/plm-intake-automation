import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import ledger, mail_threads_backfill as bf  # noqa: E402
from plm_intake.tests.test_mail_threads import O, V  # noqa: E402


def write(d, mid, po=None, thread=None):
    ev = {"type": "SHIPMENT", "vendor": "Lieferant D", "ref": {"po_number": po, "style": None, "container": None}, "date": None, "summary": "Verladung " + mid, "details": {}, "confidence": 0.9, "key": mid}
    j = {"mail_id": mid, "mail_date": "2026-10-15 10:00", "from": "kontakt@lieferant-d.example", "subject": "s", "events": [ev]}
    if thread:
        j["thread_id"] = thread
    f = Path(d) / (mid + "_events.json"); f.write_text(json.dumps(j)); return f


class Backfill(unittest.TestCase):
    def setUp(self):
        t = Path(tempfile.mkdtemp())
        self.mails, self.inbox, self.intake = t / "mails", t / "inbox", t / "intake"
        for p in (self.mails, self.inbox, self.intake):
            p.mkdir()
        (self.mails / "mails_1.txt").write_text("===== MAIL =====\nMessage-ID: m01\nThread-ID: T1\nDatum: x\n===== MAIL =====\nMessage-ID: m02\nThread-ID: T1\nDatum: y\n")
        self.ctx = {"orders": O, "vendors": V, "products": [], "style_aliases": {}}

    def test_thread_map(self):
        self.assertEqual(bf.thread_map(self.mails), {"m01": "T1", "m02": "T1"})

    def test_trockenlauf_und_apply(self):
        f_done = write(self.inbox, "m01", po="PO-LIEFERANT_D-1")
        f_open = write(self.inbox, "m02")
        led = {}; ledger.mark(led, f_done, "applied"); ledger.save(self.intake / "ledger.json", led)
        before_done = f_done.read_text()
        r = bf.run(self.inbox, self.intake, self.ctx, bf.thread_map(self.mails), dirs={})
        self.assertEqual((r["offen, wird ergaenzt"], r["erledigt (nicht angefasst)"]), (1, 1))
        self.assertEqual((r["Klaerfaelle ohne Verlauf"], r["Klaerfaelle mit Verlauf"], r["Ereignisse ueber Verlauf zugeordnet"]), (1, 0, 1))
        self.assertNotIn("thread_id", f_open.read_text()); self.assertFalse((self.intake / "mail_threads.json").exists())   # Trockenlauf schreibt nichts
        r = bf.run(self.inbox, self.intake, self.ctx, bf.thread_map(self.mails), apply=True, dirs={})
        self.assertEqual(json.loads(f_open.read_text())["thread_id"], "T1"); self.assertEqual(f_done.read_text(), before_done)   # erledigte Datei unveraendert
        self.assertEqual(json.loads((self.intake / "mail_threads.json").read_text()), {"T1": ["C1"]})


if __name__ == "__main__":
    unittest.main()
