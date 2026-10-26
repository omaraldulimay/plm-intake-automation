import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import order_attachments as oa  # noqa: E402

MAIL = "1a0cd67bc7e8f28c"


def att(display, data=b"pdf-inhalt", mail=MAIL, date="2026-10-01"):
    return {"name": "%s_%s_%s" % (date, mail, display), "size": len(data), "get": lambda d=data: d}


def doc(po, srcdoc, mail=MAIL, typ="INVOICE"):
    return {"doc_type": typ, "po_number": po, "source": {"doc": srcdoc, "mail_id": mail}}


class Plan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.inbox = Path(self.tmp.name)

    def go(self, docs, rows, files, text="Rechnung 1000 Stueck Ware nur Positionen und Mengen", overrides=None):
        for fn, d in docs.items():
            (self.inbox / fn).write_text(json.dumps(d))
        return oa.plan(self.inbox, rows, files, overrides, text_of=lambda n, b: text)

    def test_eindeutig_wird_kandidat(self):
        items, ex = self.go({"a_1.json": doc("SMI2612", "LIEFERANT_AA26104")}, [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}],
                            [att("LIEFERANT_AA26104 -invoice.pdf")])
        self.assertEqual([(i["display"], i["order_id"]) for i in items], [("LIEFERANT_AA26104 -invoice.pdf", "o1")]); self.assertEqual(ex, [])

    def test_nie_ambiguous_orphan_blocker(self):
        for kind in ("AMBIGUOUS_DOC", "ORPHAN_DOC", "BLOCKER", "SERVICE_DOC", "REORDER_QUESTION", "PI_CHANGED"):
            items, ex = self.go({"a_1.json": doc("SMI2612", "LIEFERANT_AA26104")}, [{"file": "a_1.json", "kind": kind, "pid": "o1" if kind == "REORDER_QUESTION" else None, "parent": "#3 PO-X"}],
                                [att("LIEFERANT_AA26104 -invoice.pdf")])
            self.assertEqual(items, [], kind); self.assertTrue(ex)

    def test_zahlungsnachweis_und_nicht_beleg(self):
        rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}]
        files = [att("SMI2612 payment slip.pdf"), att("SMI2612 swift copy.pdf"), att("SMI2612 BL.pdf"), att("SMI2612 invoice.png"), att("SMI2612 Preisvergleich.xlsx"),
                 att("SMI2612 final inspection.pdf"), att("SMI2612 logo.pdf")]
        items, ex = self.go({"a_1.json": doc("SMI2612", "SMI2612")}, rows, files)
        self.assertEqual(items, []); self.assertEqual(len(ex), 7)

    def test_bankdaten_des_lieferanten_erlaubt(self):
        rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}]
        for t in ("Total 5 EUR IBAN DE89 3704 0044 0532 0130 00", "pay to SWIFT: BKCHCNBJ", "Beneficiary: ACME", "x" * 5, ""):
            items, ex = self.go({"a_1.json": doc("SMI2612", "SMI2612")}, rows, [att("SMI2612 invoice.pdf")], text=t)
            self.assertEqual(len(items), 1, t)

    def test_zahlungsnachweis_im_inhalt_bleibt_aus(self):
        rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}]
        for t in ("MT103 Ordering customer Smilodox GmbH", "Payment confirmation 5000 EUR", "Remittance advice"):
            items, ex = self.go({"a_1.json": doc("SMI2612", "SMI2612")}, rows, [att("SMI2612 invoice.pdf")], text=t)
            self.assertEqual(items, [], t)

    def test_iban_swift_im_text_alte_sperre(self):
        rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}]
        old = oa.BANKDATEN_ERLAUBT; oa.BANKDATEN_ERLAUBT = False
        self.addCleanup(setattr, oa, "BANKDATEN_ERLAUBT", old)
        for t in ("Total 5 EUR IBAN DE89 3704 0044 0532 0130 00", "pay to SWIFT: BKCHCNBJ", "Beneficiary: ACME", "x" * 5):
            items, ex = self.go({"a_1.json": doc("SMI2612", "SMI2612")}, rows, [att("SMI2612 invoice.pdf")], text=t)
            self.assertEqual(items, [], t)

    def test_sperre_falsche_zuordnung(self):
        rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-LIEFERANT_AA-26WJD-107-SS26-1ST-ORDER"}]
        items, ex = self.go({"a_1.json": doc("X", "LIEFERANT_AA26104")}, rows, [att("LIEFERANT_AA26104 -invoice.pdf")])
        self.assertEqual(items, []); self.assertIn("SPERRE", ex[0][1])

    def test_sperre_lieferant_i_nur_fuer_order_96_nicht_fuer_die_neuen_orders(self):
        for srcdoc, titel, erlaubt in (("SPR2026000000422", "PO-LIEFERANT_I-SPR2026000000409", False), ("SPR2026000000422", "PO-LIEFERANT_I-SPR2026000000422", True),
                                       ("SPR2026000000438", "PO-LIEFERANT_I-SPR2026000000409", False), ("SPR2026000000438", "PO-LIEFERANT_I-SPR2026000000438", True)):
            rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#9 " + titel}]
            items, ex = self.go({"a_1.json": doc(None, srcdoc)}, rows, [att(srcdoc + ".pdf")])
            self.assertEqual(len(items), 1 if erlaubt else 0, (srcdoc, titel))
            if not erlaubt:
                self.assertIn("SPERRE", ex[0][1])

    def test_test_order_und_override_skip(self):
        r = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-ZZ-TEST"}]
        self.assertEqual(self.go({"a_1.json": doc("SMI2612", "SMI2612")}, r, [att("SMI2612 invoice.pdf")])[0], [])
        r = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}]
        self.assertEqual(self.go({"a_1.json": doc("SMI2612", "SMI2612")}, r, [att("SMI2612 invoice.pdf")], overrides={"a_1.json": "SKIP"})[0], [])

    def test_datei_zu_zwei_orders_wird_nicht_angehaengt(self):
        rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}, {"file": "a_2.json", "kind": "DELIVERY_DOC", "pid": "o2", "parent": "#4 PO-Y"}]
        items, ex = self.go({"a_1.json": doc("SMI2612", "SMI2612"), "a_2.json": doc("SMI2612", "SMI2612")}, rows, [att("SMI2612 invoice.pdf")])
        self.assertEqual(items, [])

    def test_datei_von_ambiguem_beleg_derselben_mail_blockiert(self):
        rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}, {"file": "a_2.json", "kind": "AMBIGUOUS_DOC"}]
        items, _ = self.go({"a_1.json": doc("SMI2612", "SMI2612"), "a_2.json": doc("SMI2612", "SMI2612")}, rows, [att("SMI2612 invoice.pdf")])
        self.assertEqual(items, [])

    def test_andere_mail_zaehlt_nicht(self):
        rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}]
        items, _ = self.go({"a_1.json": doc("SMI2612", "SMI2612")}, rows, [att("SMI2612 invoice.pdf", mail="ffffffffffffffff")])
        self.assertEqual(items, [])

    def test_gleicher_inhalt_zweimal_nur_einmal(self):
        rows = [{"file": "a_1.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}]
        files = [att("SMI2612 invoice.pdf", date="2026-10-01"), att("SMI2612 invoice.pdf", date="2026-10-02")]
        files[1]["name"] = files[1]["name"].replace(MAIL, "1a0cd67bc7e8f28d")
        d = doc("SMI2612", "SMI2612"); d2 = doc("SMI2612", "SMI2612", mail="1a0cd67bc7e8f28d")
        items, _ = self.go({"a_1.json": d, "a_2.json": d2}, rows + [{"file": "a_2.json", "kind": "DELIVERY_DOC", "pid": "o1", "parent": "#3 PO-X"}], files)
        self.assertEqual(len(items), 1)


def item(i, order="o1", name="Rechnung 1.pdf", data=None):
    data = data or b"daten%d" % i
    return {"file": "a_1.json", "mail": MAIL, "date": "2026-10-0%d" % (i % 9 + 1), "display": name if i == 0 else "R%d.pdf" % i, "att_file": "x", "order_id": order, "order": "PO-X",
            "sha": oa.sha1(data), "size": len(data), "data": data}


class Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.led = Path(self.tmp.name) / "l.json"
        self.store = {}   # orderId -> [attachments]
        self.up = []

    def reader(self, oids):
        return {o: list(self.store.get(o, [])) for o in oids}

    def uploader(self, oid, name, data):
        self.up.append((oid, name))
        i = "att%d" % len(self.up)
        self.store.setdefault(oid, []).append({"id": i, "name": name.rsplit(".", 1)[0]})
        return True, i

    def go(self, items, apply=True, **kw):
        return oa.run(items, [], self.led, apply, reader=self.reader, uploader=self.uploader, **kw)

    def test_dry_run_schreibt_nichts(self):
        lines, res = self.go([item(1), item(2)], apply=False)
        self.assertEqual((res["neu"], self.up, self.led.exists()), (2, [], False))

    def test_apply_ledger_und_zweiter_lauf_ohne_dubletten(self):
        its = [item(1), item(2)]
        _, res = self.go(its)
        self.assertEqual((res["neu"], res["fehler"]), (2, 0)); self.assertEqual(len(self.up), 2)
        _, res = self.go(its)
        self.assertEqual((res["neu"], res["uebersprungen"]), (0, 2)); self.assertEqual(len(self.up), 2)
        self.assertEqual(len(json.loads(self.led.read_text())["done"]), 2)

    def test_name_im_plm_vorhanden_wird_uebersprungen(self):
        self.store["o1"] = [{"id": "m", "name": "R1"}]
        _, res = self.go([item(1)])
        self.assertEqual((res["neu"], res["uebersprungen"], self.up), (0, 1, []))

    def test_gleicher_name_anderer_inhalt_aus_ledger_bekommt_datum(self):
        a, b = item(1), item(1, data=b"anderer inhalt"); b["date"] = "2026-10-20"
        self.go([a]); self.up.clear()
        _, res = self.go([b])
        self.assertEqual(res["neu"], 1); self.assertEqual(self.up[0][1], "R1 (2026-10-20).pdf")

    def test_max_30_pro_lauf(self):
        its = [item(i + 1, name="x") for i in range(45)]
        for n, it in enumerate(its): it["display"] = "F%d.pdf" % n
        _, res = self.go(its, max_files=99)
        self.assertEqual((res["neu"], res["offen"], len(self.up)), (30, 15, 30))

    def test_zuruecklesen_abweichung_bricht_ab(self):
        orig = self.uploader
        def bad(oid, name, data):
            ok, i = orig(oid, name, data); self.store[oid].pop(); return ok, i
        its = [item(i + 1) for i in range(25)]
        _, res = oa.run(its, [], self.led, True, reader=self.reader, uploader=bad)
        self.assertEqual(len(self.up), 10); self.assertEqual(res["fehler"], 10); self.assertEqual(res["neu"], 0)

    def test_upload_fehler_zaehlt_und_stoppt_nach_block(self):
        _, res = oa.run([item(1), item(2)], [], self.led, True, reader=self.reader, uploader=lambda o, n, d: (False, "presign 403"))
        self.assertEqual((res["neu"], res["fehler"]), (0, 2)); self.assertEqual(oa.report_line(res), "Anhaenge: neu 0, uebersprungen 0, Fehler 2")


if __name__ == "__main__":
    unittest.main()
