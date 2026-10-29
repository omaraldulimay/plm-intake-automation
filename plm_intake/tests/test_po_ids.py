import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import docs_existing, events, po_ids  # noqa: E402

O36 = {"id": "O36", "orderNumber": 36, "createdAt": "2026-07-01T10:00:00.000Z", "title": "PO-XW-SM260730", "manufacturer": {"id": "V_XW"}, "items": [], "status": {"status": "In Progress"}}
O37 = {"id": "O37", "orderNumber": 37, "createdAt": "2026-07-02T10:00:00.000Z", "title": "PO-LIEFERANT_D-1", "manufacturer": {"id": "V_CM"}, "items": [], "status": {"status": "Complete"}}
OT = {"id": "OT", "orderNumber": 90, "createdAt": "2026-10-01T10:00:00.000Z", "title": "ZZ-TEST-1", "manufacturer": {"id": "V_XW"}, "items": []}
ORDERS = [O36, O37, OT]



def setUpModule():
    from plm_intake import po_ids
    po_ids.set_registry(None)   # Registry ist global: Tests laufen im alten Format


def tearDownModule():
    from plm_intake import po_ids
    po_ids.set_registry(None)

class PoIds(unittest.TestCase):
    def test_format_and_year(self):
        self.assertEqual(po_ids.po_id(O36), "PO26-036")
        self.assertEqual(po_ids.po_id({"orderNumber": 5, "createdAt": "1792581106662"}), "PO26-005")
        self.assertEqual(po_ids.po_id({"orderNumber": 123, "createdAt": "2027-01-01T00:30:00Z"}), "PO27-123")
        self.assertEqual(po_ids.po_id({"orderNumber": 1, "createdAt": "2026-12-31T23:30:00Z"}), "PO27-001")   # Berlin-Zeit

    def test_test_orders(self):
        for t in ("ZZ-TEST-1", "PO-X-T1-2", "Mein TEST"):
            self.assertTrue(po_ids.is_test(t))
        self.assertFalse(po_ids.is_test("PO-XW-SM260730"))
        self.assertNotIn("PO26-090", po_ids.by_po_id(ORDERS))

    def test_find_pattern(self):
        self.assertEqual(po_ids.find_po_ids("Re: PO26-036 und po26-037, PO26-0361"), ["PO26-036", "PO26-037"])
        self.assertEqual(po_ids.find_po_ids("XPO26-036"), [])

    def test_plan_no_overwrite(self):
        cur = {"O36": {"v": None}, "O37": {"v": "PO26-999"}, "OT": {"v": None}}
        todo, ok, wrong, skipped = po_ids.plan(ORDERS, cur)
        self.assertEqual([(o["id"], p) for o, p in todo], [("O36", "PO26-036")])
        self.assertEqual([(o["id"], s, i) for o, s, i in wrong], [("O37", "PO26-037", "PO26-999")])
        self.assertEqual([o["id"] for o in skipped], ["OT"])

    def test_backfill_writes_and_verifies(self):
        calls = []

        def runner(js):
            calls.append(js)
            if "for(const j of" in js:
                return [{"id": "O36", "v": "PO26-036", "same": True}, {"id": "O37", "v": "PO26-037", "same": True}]
            return {"O36": {"v": None}, "O37": {"v": None}}
        res = po_ids.backfill(ORDERS, apply=False, runner=runner)
        self.assertEqual(len(res["todo"]), 2); self.assertEqual(res["written"], 0)
        self.assertEqual(len(calls), 1)   # Trockenlauf liest nur

    def test_find_order_by_po_id(self):
        e = {"type": "SCHEDULE", "vendor": "Lieferant D", "ref": {"po_number": None}, "summary": "ETD fuer PO26-036 verschoben", "details": {}, "_mail": {"subject": "x"}}
        o, how = events.find_order(e, ORDERS, [{"id": "V_XW", "name": "Xiamen"}, {"id": "V_CM", "name": "Lieferant D"}])
        self.assertEqual((o["id"], how), ("O36", "po_id"))

    def test_find_order_po_id_beats_alias(self):
        e = {"type": "SCHEDULE", "vendor": "x", "ref": {"po_number": "PO26-036"}, "details": {}, "_mail": {}}
        o, how = events.find_order(e, ORDERS, [], aliases={"PO26-036": "PO-LIEFERANT_D-1"})
        self.assertEqual((o["id"], how), ("O36", "po_id"))

    def test_unknown_po_id_ignored(self):
        self.assertIsNone(po_ids.order_for_text(ORDERS, "PO26-500"))
        self.assertIsNone(po_ids.order_for_text(ORDERS, "PO26-036 PO26-037"))   # zwei verschiedene = nicht eindeutig

    def test_parent_for(self):
        p, amb = docs_existing.parent_for({"id": "V_XW"}, {"po_number": None, "summary": "Rechnung zu PO26-036"}, ORDERS, {})
        self.assertEqual(p["id"], "O36")
        p, amb = docs_existing.parent_for({"id": "V_CM"}, {"po_number": "PO26-036"}, ORDERS, {})   # Lieferant passt nicht -> nicht direkt zuordnen
        self.assertNotEqual((p or {}).get("id"), "O36")

    def test_new_format_registry(self):
        codes = {"V_XW": "LFC", "V_CM": "LFD"}
        a = {"id": "A", "orderNumber": 1, "title": "a", "manufacturer": {"id": "V_XW"}, "createdAt": "2026-07-01T10:00:00Z"}
        b = {"id": "B", "orderNumber": 2, "title": "b", "manufacturer": {"id": "V_XW"}, "createdAt": "2026-07-02T10:00:00Z"}
        c = {"id": "C", "orderNumber": 3, "title": "c", "manufacturer": {"id": "V_CM"}, "createdAt": "2026-07-03T10:00:00Z"}
        n = {"id": "N", "orderNumber": 4, "title": "n", "manufacturer": {"id": "V_NO"}, "createdAt": "2026-07-04T10:00:00Z"}
        reg, miss = po_ids.assign([a, b, c, n, OT], codes, {})
        self.assertEqual((reg["A"], reg["B"], reg["C"]), ("PO-LFC-01", "PO-LFC-02", "PO-LFD-01"))
        self.assertEqual(miss, ["n"]); self.assertNotIn("OT", reg)
        d = {"id": "D", "orderNumber": 5, "title": "d", "manufacturer": {"id": "V_XW"}, "createdAt": "2026-07-05T10:00:00Z"}
        reg2, _ = po_ids.assign([a, c, d], codes, reg)   # B geloescht: Nummern bleiben, D bekommt 03
        self.assertEqual((reg2["A"], reg2["D"]), ("PO-LFC-01", "PO-LFC-03"))
        po_ids.set_registry(reg2)
        try:
            self.assertEqual(po_ids.po_id(a), "PO-LFC-01")
            self.assertEqual(po_ids.find_po_ids("Re: po-lfc-1 / PO-LFC-02x PO-LFC-03 und PO26-036"), ["PO-LFC-01", "PO-LFC-03", "PO26-036"])   # PO-LFC-1 wird zu 01; -02x zaehlt nicht
            self.assertEqual(po_ids.norm_po("PO-lfc-3"), "PO-LFC-03")
            self.assertIs(po_ids.order_for_text([a, c, d], "Rechnung PO-LFD-01")["id"], "C")
            self.assertEqual(po_ids.order_for_text([a, c, d], "alt PO26-005")["id"], "D")   # altes Format fuehrt weiter zur Bestellung
            cur = {"A": {"v": "PO26-001"}, "C": {"v": "PO-LFD-01"}, "D": {"v": None}}
            todo, ok, wrong, _ = po_ids.plan([a, c, d], cur)
            self.assertEqual(sorted(o["id"] for o, _p in todo), ["A", "D"])   # alter Wert wird migriert, richtiger bleibt
            self.assertEqual([o["id"] for o in ok], ["C"])
        finally:
            po_ids.set_registry(None)

    def test_supplier_md(self):
        md = po_ids.supplier_md(ORDERS, {"O36": "SM260730"}, today="2026-10-22")
        self.assertIn("PO26-036", md); self.assertIn("SM260730", md)
        self.assertNotIn("PO26-037", md)   # Complete
        self.assertNotIn("ZZ-TEST", md)


if __name__ == "__main__":
    unittest.main()
