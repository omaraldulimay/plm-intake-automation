import copy
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import core  # noqa: E402

TODAY = dt.date(2026, 10, 14)
VENDORS = [{"id": "V_XW", "name": "Lieferant C"}, {"id": "V_LIEFERANT_AA", "name": "LIEFERANT_AA"}, {"id": "V_LIEFERANT_AG", "name": "Lieferant AG"},
           {"id": "V_MIU", "name": "Xiamen Lieferant G Industry Co., Ltd"}, {"id": "V_LIEFERANT_D", "name": "Ningbo Lieferant D Co., Ltd"},
           {"id": "V_A1", "name": "Lieferant A"}, {"id": "V_A2", "name": "Lieferant A Exports"}]
PRODUCTS = [
    {"id": "P41", "sku": "XW-041", "sizes": ["S", "M", "L", "XL", "XXL", "3XXL"],
     "variants": [{"id": "P41B", "name": "Black"}, {"id": "P41Y", "name": "Yellow"}, {"id": "P41G", "name": "Grey green"}]},
    {"id": "P124", "sku": "XW-124", "sizes": ["S", "M", "L", "XL", "2XL", "3XXL"],
     "variants": [{"id": "P124B", "name": "Black"}, {"id": "P124N", "name": "Navy"}, {"id": "P124C", "name": "Creme"}]},
]
ORDERS = [{"id": "O28", "orderNumber": 28, "title": "PO-XW-SM260513", "poNumber": "XW-SM260513", "manufacturer": {"id": "V_XW"},
           "totalCost": 176626.65, "totalNumberOfPieces": 18587},
          {"id": "O4", "orderNumber": 4, "title": "PO-LIEFERANT_X-JM260704", "manufacturer": {"id": "V_LIEFERANT_X"}, "totalCost": 60906.5, "totalNumberOfPieces": 3620}]
CTX = {"vendors": VENDORS, "products": PRODUCTS, "orders": ORDERS}


def po(**kw):
    base = {"source": {"doc": "PI XW-SM260999", "mail_id": "m1"}, "vendor": "Lieferant C Co., Ltd.", "po_number": "XW-SM260999",
            "currency": "USD", "ex_factory": "2026-09-15", "etd": "2026-09-27",
            "items": [{"sku": "XW-041", "name": "XW-041 Men Windbreaker",
                       "variants": [{"color": "Black", "price": 10.0, "sizes": {"S": 10, "M": 20, "2XL": 5, "3XL": 5}}]}],
            "payments": [{"name": "30%", "status": "Paid", "amount": 120.0, "due": "2026-08-01"},
                         {"name": "70%", "status": "Unpaid", "amount": 280.0, "due": "22.09.2026"}]}
    base.update(kw)
    return base


def codes(res): return {i.code for i in res.issues}


class Normalisierung(unittest.TestCase):
    def test_vendor_exakt_und_fuzzy(self):
        v, why = core.match_vendor("Lieferant C Co., Ltd.", VENDORS)
        self.assertEqual((v["id"], why), ("V_XW", "fuzzy"))
        v, why = core.match_vendor("LIEFERANT_AA", VENDORS)
        self.assertEqual((v["id"], why), ("V_LIEFERANT_AA", "exact"))
        v, why = core.match_vendor("Ningbo Lieferant D Co., Ltd", VENDORS)
        self.assertEqual(v["id"], "V_LIEFERANT_D")

    def test_vendor_mehrdeutig_oder_unbekannt(self):
        v, why = core.match_vendor("Lieferant A Pvt Ltd", VENDORS)
        self.assertIsNone(v)
        self.assertIn("mehrdeutig", why)
        v, _ = core.match_vendor("Voellig Anderer", VENDORS)
        self.assertIsNone(v)

    def test_farben(self):
        for raw, exp in [("Schwarz", "black"), ("Navy19-3815TCX", "navy"), ("Anthrazite 19-3907TCX", "anthracite"),
                         ("Grey green 15-4306TCX", "grey green"), ("Creme 11-0606TCX", "cream"), ("Dunkelblau", "navy"), ("Schwarz (GT0301-A1)", "black"), ("Wine Red (former Bordeaux)", "wine red"), ("Taupe (GT0302-C1)", "taupe")]:
            self.assertEqual(core.norm_color(raw), exp, raw)

    def test_groessen(self):
        ps = ["S", "M", "L", "XL", "XXL", "3XXL"]
        self.assertEqual(core.map_size("2XL", ps), "XXL")
        self.assertEqual(core.map_size("3XL", ps), "3XXL")
        self.assertEqual(core.map_size("xl", ps), "XL")
        self.assertEqual(core.map_size("XXL", ["S", "2XL"]), "2XL")
        self.assertIsNone(core.map_size("5XL", ps))
        self.assertIsNone(core.map_size("S", None))

    def test_datum(self):
        d = dt.date(2026, 9, 29)
        for raw in ["2026-09-29", "29.09.2026", "29/Sep/26", "29/09/2026"]:
            self.assertEqual(core.parse_date(raw), d, raw)
        self.assertIsNone(core.parse_date("bald"))
        self.assertEqual(core.ms(dt.date(2026, 9, 22)), 1790035200000)   # = Wert aus echter PO #28

    def test_titel(self):
        self.assertEqual(core.make_title("Lieferant C Co., Ltd.", "XW-SM260999"), "PO-LIEFERANT_C-XW-SM260999")


class Anlegen(unittest.TestCase):
    def test_normalfall_create_mit_verknuepfung_und_groessen(self):
        r = core.build(po(), CTX, TODAY)
        self.assertEqual(r.decision, "CREATE", [i.msg for i in r.issues])
        p = r.payload
        self.assertEqual(p["manufacturer"], "V_XW")
        it = p["items"][0]
        self.assertEqual(it["product"], "P41")
        self.assertEqual(it["variants"][0]["variantId"], "P41B")
        self.assertEqual({a["key"] for a in it["variants"][0]["amounts"]}, {"S", "M", "XXL", "3XXL"})
        self.assertEqual((p["totalCost"], p["totalNumberOfPieces"]), (400.0, 40))
        self.assertEqual(p["payments"][1]["dueDate"], 1790035200000)
        self.assertEqual(p["exFactoryExpectedDate"], "2026-09-15T00:00:00.000Z")
        self.assertIn("vendor_fuzzy", codes(r))

    def test_echtfall_xw_sm260513_groessen_ohne_verlust(self):
        # Black XW-124: 3480 Stk x 11.9, Groessen 2XL/3XL -> Produkt hat 2XL/3XXL
        x = po(po_number="XW-SM260514", source={"doc": "t"}, items=[{"sku": "XW-124", "name": "XW-124", "variants": [
            {"color": "Black", "price": 11.9, "sizes": {"S": 402, "M": 1158, "L": 1200, "XL": 360, "XXL": 222, "3XL": 138}}]}],
            payments=[{"name": "alles", "status": "Unpaid", "amount": 41412.0, "due": "2026-09-22"}])
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.decision, "CREATE", [i.msg for i in r.issues])
        keys = [a["key"] for a in r.payload["items"][0]["variants"][0]["amounts"]]
        self.assertEqual(keys, ["S", "M", "L", "XL", "2XL", "3XXL"])
        self.assertEqual(r.payload["totalCost"], 41412.0)
        self.assertEqual(r.payload["totalNumberOfPieces"], 3480)

    def test_unbekanntes_produkt_wird_ohne_link_angelegt(self):
        x = po(items=[{"sku": "XW26-006", "name": "XW26-006 Tee", "variants": [{"color": "Black", "price": 7.15, "sizes": {"S": 100, "M": 100}}]}],
               payments=[{"name": "all", "status": "Unpaid", "amount": 1430.0, "due": "2026-09-22"}])
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.decision, "CREATE")
        self.assertNotIn("product", r.payload["items"][0])
        self.assertIn("Produkt XW26-006 ohne Verknuepfung", r.payload["notes"])

    def test_unbekannte_farbe_am_bekannten_produkt(self):
        x = po(items=[{"sku": "XW-041", "name": "n", "variants": [{"color": "Pink", "price": 1.0, "sizes": {"S": 400}}]}],
               payments=[{"name": "p", "status": "Unpaid", "amount": 400.0, "due": "2026-09-22"}])
        r = core.build(x, CTX, TODAY)
        self.assertIn("color_unlinked", codes(r))
        self.assertNotIn("variantId", r.payload["items"][0]["variants"][0])
        self.assertEqual(r.decision, "CREATE")

    def test_fehlende_groessen_termine_platzhalter_und_offen(self):
        x = po(items=[{"sku": None, "name": "Socken", "variants": [{"color": "Leo", "price": 1.5, "quantity": 800}]}],
               payments=[], ex_factory=None, etd=None)
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.decision, "CREATE", [i.msg for i in r.issues])
        a = r.payload["items"][0]["variants"][0]["amounts"][0]
        self.assertEqual((a["key"], a["price"], a["cost"]), ("ONE SIZE", 1.5, 1200.0))
        self.assertNotIn("exFactoryExpectedDate", r.payload)
        self.assertIn("Offen:", r.payload["notes"])

    def test_preis_fehlt_oder_null_wird_angelegt_mit_notiz(self):
        for price in (None, 0, 0.0):
            x = po(items=[{"sku": None, "name": "Socken", "variants": [{"color": "Leo", "price": price, "sizes": {"S": 800}}]}], total_cost=None)
            r = core.build(x, CTX, TODAY)
            self.assertEqual(r.decision, "CREATE", [i.msg for i in r.issues])
            self.assertIn(("WARN", "price_missing"), [(i.level, i.code) for i in r.issues])
            self.assertFalse([i for i in r.issues if i.level == "ERROR"])
            self.assertEqual(r.payload["totalCost"], 0)
            self.assertEqual(r.payload["items"][0]["variants"][0]["amounts"][0]["price"], 0.0)
            self.assertIn("PREIS AUSSTEHEND (Beleg ohne Preis, Stand %s)" % TODAY, r.payload["notes"])
        x = po(items=[{"sku": None, "name": "Socken", "variants": [{"color": "Leo", "sizes": {"S": 800}}]}], total_cost=None)
        self.assertEqual(core.build(x, CTX, TODAY, force_create=True).decision, "CREATE")

    def test_preis_fehlt_leere_oder_kleine_bestellung_bleibt_block(self):
        x = po(items=[{"sku": None, "name": "Socken", "variants": [{"color": "Leo", "price": 0, "sizes": {"S": 3}}]}], total_cost=None)
        self.assertIn("too_small", [i.code for i in core.build(x, CTX, TODAY).issues if i.level == "ERROR"])
        x = po(items=[{"sku": None, "name": "Socken", "variants": [{"color": "Leo", "price": 0, "sizes": {}}]}], total_cost=None)
        self.assertEqual(core.build(x, CTX, TODAY).decision, "BLOCK")

    def test_mit_preis_keine_preis_ausstehend_notiz(self):
        r = core.build(po(), CTX, TODAY)
        self.assertNotIn("PREIS AUSSTEHEND", r.payload["notes"])

    def test_zahlung_ohne_termin_bekommt_platzhalter(self):
        x = po(payments=[{"name": "a", "status": "Paid", "amount": 400.0}])
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.payload["payments"][0]["dueDate"], core.ms(dt.date(2026, 9, 15)))
        self.assertIn("Zahlungstermin Platzhalter", r.payload["notes"])

    def test_euro_bleibt_euro(self):
        r = core.build(po(currency="eur"), CTX, TODAY)
        self.assertEqual(r.payload["currency"], "EUR")

    def test_nullmengen_werden_verworfen_gleiche_groessen_summiert(self):
        x = po(items=[{"sku": "XW-041", "name": "n", "variants": [{"color": "Black", "price": 1.0, "sizes": {"S": 0, "XXL": 5, "2XL": 5, "M": 390}}]}],
               payments=[{"name": "p", "status": "Unpaid", "amount": 400.0, "due": "2026-09-22"}])
        r = core.build(x, CTX, TODAY)
        am = {a["key"]: a["quantity"] for a in r.payload["items"][0]["variants"][0]["amounts"]}
        self.assertEqual(am, {"XXL": 10, "M": 390})

    def test_mehrmenge_gegenueber_vertrag_ist_warnung_mit_notiz(self):
        x = po(contract_total=380.0)
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.decision, "CREATE")
        self.assertIn("contract_diff", codes(r))
        self.assertIn("Abweichung zum vereinbarten Wert", r.payload["notes"])


class Sperren(unittest.TestCase):
    def blocked(self, x, code):
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.decision, "BLOCK", [i.msg for i in r.issues])
        self.assertIn(code, codes(r))

    def test_vendor_unbekannt(self): self.blocked(po(vendor="Neue Firma Ltd"), "vendor_unknown")
    def test_vendor_mehrdeutig(self): self.blocked(po(vendor="Lieferant A Pvt Ltd"), "vendor_unknown")
    def test_vendor_fehlt(self): self.blocked(po(vendor=None), "vendor_missing")
    def test_po_nummer_fehlt(self): self.blocked(po(po_number=" "), "po_number_missing")
    def test_waehrung_unbekannt(self): self.blocked(po(currency="XYZ"), "currency")
    def test_keine_positionen(self): self.blocked(po(items=[]), "no_items")
    def unstimmig(self, x, code):
        """Unstimmigkeit sperrt die Bestellung nicht mehr: sie wird mit den Positionen angelegt, die Abweichung steht als UNSTIMMIG in den Notizen."""
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.decision, "CREATE", [i.msg for i in r.issues])
        self.assertIn(code, [i.code for i in r.issues if i.level == "WARN"])
        self.assertIn("UNSTIMMIG", r.payload["notes"])

    def test_leere_positionen_gesperrt(self):
        r = core.build(po(items=[{"sku": "XW-041", "name": "n", "variants": [{"color": "Black", "price": 1.0, "sizes": {"S": 0}}]}], total_cost=2.0, total_pieces=1), CTX, TODAY)
        self.assertEqual(r.decision, "BLOCK")
        self.assertIn("empty_order", codes(r))

    def test_ein_stueck_gesperrt(self):
        self.blocked(po(items=[{"sku": "XW-041", "name": "n", "variants": [{"color": "Black", "price": 2.0, "sizes": {"S": 1}}]}],
                        total_cost=None, total_pieces=None, payments=[]), "too_small")

    def test_muster_zollbeleg_gesperrt(self):
        items = [{"sku": None, "name": "TRIM CARDS", "variants": [{"color": None, "price": 2.0, "sizes": {"ONE SIZE": 20}}]}]
        r = core.build(po(items=items, total_cost=None, total_pieces=None, payments=[], notes="Zoll-Proforma-Rechnung fuer ein Muster (Reason/Type of Export: Sample), kein regulaerer Bestellvorgang."), CTX, TODAY)
        self.assertEqual(r.decision, "BLOCK")
        self.assertIn("sample_doc", codes(r))
        big = [{"sku": None, "name": "Hose", "variants": [{"color": None, "price": 2.0, "sizes": {"S": 500}}]}]   # echte PI mit Musterzeile bleibt moeglich
        r = core.build(po(items=big, total_cost=None, total_pieces=None, payments=[], notes="Reason for Export: Sample charge separate"), CTX, TODAY)
        self.assertNotIn("sample_doc", codes(r))

    def test_summe_stimmt_nicht(self): self.unstimmig(po(total_cost=999.0), "sum_mismatch")
    def test_stueckzahl_stimmt_nicht(self): self.unstimmig(po(total_pieces=41), "pieces_mismatch")
    def test_zahlungssumme_stimmt_nicht(self):
        self.unstimmig(po(payments=[{"name": "x", "status": "Unpaid", "amount": 100.0, "due": "2026-09-22"}]), "payment_sum")
    def test_zahlungsstatus_ungueltig(self):
        self.blocked(po(payments=[{"name": "x", "status": "Bezahlt", "amount": 400.0, "due": "2026-09-22"}]), "payment_status")
    def test_negative_menge(self):
        self.blocked(po(items=[{"sku": "XW-041", "name": "n", "variants": [{"color": "Black", "price": 1.0, "sizes": {"S": -4}}]}]), "qty_invalid")
    def test_halbe_menge(self):
        self.blocked(po(items=[{"sku": "XW-041", "name": "n", "variants": [{"color": "Black", "price": 1.0, "sizes": {"S": 2.5}}]}]), "qty_invalid")
    def test_negativer_preis(self):
        self.blocked(po(items=[{"sku": "XW-041", "name": "n", "variants": [{"color": "Black", "price": -1.0, "sizes": {"S": 4}}]}],
                        payments=[]), "price_negative")

    def test_bankdaten_in_notes_werden_gesperrt(self):
        for txt in ["Zahlung an IBAN DE89 3704 0044 0532 0130 00", "Beneficiary A/C NO: 1294 1140", "SWIFT CODE: FJIBCNBA260", "Account number 12345"]:
            self.blocked(po(notes=txt), "bank_data")

    def test_sicherheitsnetz_summen_unabhaengig_vom_input(self):
        # Rundungsfall: 3 x 0.1 * 7 -> 2.1 (nicht 2.0999999..)
        x = po(items=[{"sku": None, "name": "n", "variants": [{"color": "a", "price": 0.1, "sizes": {"S": 7, "M": 7}}]}],
               payments=[{"name": "p", "status": "Unpaid", "amount": 1.4, "due": "2026-09-22"}], total_cost=1.4, total_pieces=None)
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.decision, "CREATE", [i.msg for i in r.issues])
        self.assertEqual(r.payload["totalCost"], 1.4)


class Dubletten(unittest.TestCase):
    def test_gleiche_po_gleiche_daten_skip(self):
        x = po(po_number="XW-SM260513", items=[{"sku": None, "name": "n", "variants": [{"color": "a", "price": 1.0, "sizes": {"S": 18587}}]}],
               payments=[{"name": "p", "status": "Unpaid", "amount": 18587.0, "due": "2026-09-22"}])
        # Summe passt nicht zu #28 (176626.65) -> Update, nicht Skip
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.decision, "UPDATE")
        self.assertEqual(r.existing_id, "O28")

    def test_identische_order_wird_uebersprungen(self):
        x = po(po_number="XW-SM260513", items=[{"sku": None, "name": "n", "variants": [{"color": "a", "price": 1.0, "sizes": {"S": 18587}}]}],
               payments=[{"name": "p", "status": "Unpaid", "amount": 18587.0, "due": "2026-09-22"}])
        ctx = copy.deepcopy(CTX)
        ctx["orders"][0]["totalCost"] = 18587.0
        r = core.build(x, ctx, TODAY)
        self.assertEqual(r.decision, "SKIP")

    def test_gleiche_nummer_anderer_vendor_ist_keine_dublette(self):
        x = po(vendor="LIEFERANT_AA", po_number="XW-SM260513")
        r = core.build(x, CTX, TODAY)
        self.assertEqual(r.decision, "CREATE")

    def test_po_nummer_im_titel_alter_orders_wird_erkannt(self):
        ctx = copy.deepcopy(CTX)
        ctx["orders"].append({"id": "OJ", "orderNumber": 9, "title": "PO-LIEFERANT_AA-26WJD-108-REORDER", "manufacturer": {"id": "V_LIEFERANT_AA"},
                              "totalCost": 430476.5, "totalNumberOfPieces": 43222})
        x = po(vendor="LIEFERANT_AA", po_number="26WJD-108")
        r = core.build(x, ctx, TODAY)
        self.assertIn(r.decision, ("UPDATE", "SKIP"))
        self.assertEqual(r.existing_id, "OJ")

    def test_gleicher_vendor_summe_stueck_ohne_nummer_match(self):
        ctx = copy.deepcopy(CTX)
        ctx["orders"].append({"id": "OZ", "orderNumber": 40, "title": "irgendein Titel", "manufacturer": {"id": "V_XW"},
                              "totalCost": 400.0, "totalNumberOfPieces": 40})
        r = core.build(po(), ctx, TODAY)
        self.assertEqual(r.decision, "SKIP")
        self.assertEqual(r.existing_id, "OZ")

    def test_gleicher_titel_wird_erkannt(self):
        ctx = copy.deepcopy(CTX)
        ctx["orders"].append({"id": "OT", "orderNumber": 41, "title": "PO-LIEFERANT_C-XW-SM260999", "manufacturer": {"id": "V_OTHER"},
                              "totalCost": 1.0, "totalNumberOfPieces": 1})
        r = core.build(po(), ctx, TODAY)
        self.assertEqual(r.decision, "UPDATE")


class Packliste(unittest.TestCase):
    def test_packliste_legt_nie_eine_neue_order_an(self):
        r = core.build(po(doc_type="PACKING_LIST", po_number="NEU-12345"), CTX, TODAY)
        self.assertEqual(r.decision, "BLOCK"); self.assertIn("delivery_document_only", codes(r))

    def test_packliste_zu_bestehender_order_geht_als_update_zur_pruefung(self):
        x = po(doc_type="PACKING_LIST", po_number="XW-SM260513", items=[{"sku": None, "name": "n", "variants": [{"color": "a", "price": 1.0, "sizes": {"S": 5000}}]}],
               payments=[{"name": "p", "status": "Unpaid", "amount": 5000.0, "due": "2026-09-22"}])
        self.assertEqual(core.build(x, CTX, TODAY).decision, "UPDATE")

    def test_pi_wird_weiterhin_normal_angelegt(self):
        self.assertEqual(core.build(po(doc_type="PI"), CTX, TODAY).decision, "CREATE")


class Rechnungen(unittest.TestCase):
    def test_rechnung_wird_nie_als_neue_bestellung_angelegt(self):
        r = core.build(po(doc_type="INVOICE", po_number="NEU-12345"), CTX, TODAY)
        self.assertEqual(r.decision, "BLOCK"); self.assertIn("delivery_document_only", codes(r))

    def test_teillieferungs_rechnung_nennt_die_eltern_po(self):
        ctx = copy.deepcopy(CTX)
        ctx["orders"].append({"id": "OC", "orderNumber": 25, "title": "PO-LIEFERANT_D-ALI20260821", "manufacturer": {"id": "V_LIEFERANT_D"}, "totalCost": 347755.5, "totalNumberOfPieces": 133900})
        for suffix in ("-SEA", "-AIR", "-TRAIN"):
            r = core.build(po(doc_type="INVOICE", vendor="Ningbo Lieferant D Co., Ltd", po_number="LIEFERANT_D-ALI20260821" + suffix), ctx, TODAY)
            self.assertEqual(r.decision, "BLOCK"); self.assertEqual(r.existing_id, "OC")
            self.assertTrue(any("Order #25" in i.msg for i in r.issues))

    def test_eltern_po_nur_beim_gleichen_lieferanten(self):
        ctx = copy.deepcopy(CTX)
        ctx["orders"].append({"id": "OC", "orderNumber": 25, "title": "PO-LIEFERANT_D-ALI20260821", "manufacturer": {"id": "V_LIEFERANT_D"}, "totalCost": 1.0, "totalNumberOfPieces": 1})
        r = core.build(po(doc_type="INVOICE", vendor="LIEFERANT_AA", po_number="LIEFERANT_D-ALI20260821-SEA"), ctx, TODAY)
        self.assertIsNone(r.existing_id)

    def test_kurze_nummern_werden_nicht_als_eltern_geraten(self):
        ctx = copy.deepcopy(CTX); ctx["orders"].append({"id": "O1", "orderNumber": 1, "title": "PO-AB1", "manufacturer": {"id": "V_LIEFERANT_AA"}})
        self.assertIsNone(core.find_parent("V_LIEFERANT_AA", "AB12345", ctx["orders"]))

    def test_pi_und_po_werden_weiter_normal_angelegt(self):
        for dt in ("PI", "PO", None):
            kw = {"doc_type": dt} if dt else {}
            self.assertEqual(core.build(po(**kw), CTX, TODAY).decision, "CREATE", dt)


class Stylewache(unittest.TestCase):
    def ctx_with(self, items, vendor="V_XW"):
        c = copy.deepcopy(CTX); c["orders"].append({"id": "OX", "orderNumber": 77, "title": "PO-ALT", "manufacturer": {"id": vendor}, "items": items, "totalCost": 1.0, "totalNumberOfPieces": 1}); return c

    def test_gleicher_lieferant_gleicher_style_wird_nicht_automatisch_angelegt(self):
        c = self.ctx_with([{"name": "XW-041 Men Windbreaker", "product": None, "variants": []}])
        r = core.build(po(po_number="XW-NEU-1"), c, TODAY)
        self.assertEqual(r.decision, "BLOCK"); self.assertIn("style_overlap", codes(r)); self.assertEqual(r.existing_id, "OX")

    def test_style_ueber_das_verknuepfte_produkt_erkannt(self):
        c = self.ctx_with([{"name": "Men Windbreaker ohne Nummer", "product": {"id": "P41"}, "variants": []}])
        self.assertEqual(core.build(po(po_number="XW-NEU-2"), c, TODAY).decision, "BLOCK")

    def test_anderer_lieferant_mit_gleichem_style_ist_kein_treffer(self):
        c = self.ctx_with([{"name": "XW-041 Men Windbreaker", "variants": []}], vendor="V_LIEFERANT_AA")
        self.assertEqual(core.build(po(po_number="XW-NEU-3"), c, TODAY).decision, "CREATE")

    def test_variantenschreibweise_des_styles_wird_erkannt(self):
        c = self.ctx_with([{"name": "HY29582 KNITTED HALF-PLACKET", "variants": []}])
        r = core.build(po(po_number="NEU-5", items=[{"sku": "HY29582-Z-A", "name": "MEN'S HALF ZIPPER", "variants": [{"color": "x", "price": 1.0, "sizes": {"S": 400}}]}],
                          payments=[{"name": "p", "status": "Unpaid", "amount": 400.0, "due": "2026-09-22"}]), c, TODAY)
        self.assertEqual(r.decision, "BLOCK"); self.assertIn("style_overlap", codes(r))

    def test_aehnliche_aber_unterschiedliche_styles_sind_kein_treffer(self):
        c = self.ctx_with([{"name": "AB1234 Foo", "variants": []}])
        self.assertEqual(core.build(po(po_number="NEU-6", items=[{"sku": "ZY9999", "name": "Bar", "variants": [{"color": "x", "price": 1.0, "sizes": {"S": 400}}]}],
                          payments=[{"name": "p", "status": "Unpaid", "amount": 400.0, "due": "2026-09-22"}]), c, TODAY).decision, "CREATE")

    def test_ganz_neue_styles_werden_angelegt(self):
        c = self.ctx_with([{"name": "ZZ-999 Etwas anderes", "variants": []}])
        self.assertEqual(core.build(po(po_number="XW-NEU-4"), c, TODAY).decision, "CREATE")

    def test_bestehende_order_hat_vorrang_vor_der_stylewache(self):
        # gleiche PO-Nr existiert schon -> UPDATE/SKIP wie bisher, nicht BLOCK wegen Style
        r = core.build(po(po_number="XW-SM260513"), self.ctx_with([{"name": "XW-041 X", "variants": []}]), TODAY)
        self.assertIn(r.decision, ("UPDATE", "SKIP"))


class Eingabe(unittest.TestCase):
    def test_eingabe_wird_nicht_veraendert(self):
        x = po()
        before = copy.deepcopy(x)
        core.build(x, CTX, TODAY)
        self.assertEqual(x, before)

    def test_payload_hat_alle_pflichtfelder_von_orderinput(self):
        p = core.build(po(), CTX, TODAY).payload
        for k in ("title", "items", "payments", "assignees", "totalCost", "totalNumberOfPieces", "manufacturer"):
            self.assertIn(k, p)
        for it in p["items"]:
            self.assertIn("name", it)
            for v in it["variants"]:
                for a in v["amounts"]:
                    self.assertEqual(set(a), {"key", "quantity", "price", "cost"})
                    self.assertAlmostEqual(a["cost"], round(a["quantity"] * a["price"], 2))


class ProduktInfo(unittest.TestCase):
    def test_specs_incoterm_shipto(self):
        d = po(incoterm="FOB", eta="2026-11-20", ship_to="Lager 1, Berlin")
        d["items"][0]["product_info"] = {"barcode": "4012345678901", "uvp": 49.9, "size_run": ["S", "M"], "material": None}
        r = core.build(d, CTX, TODAY)
        self.assertEqual(r.product_specs, [{"sku": "XW-041", "linked_product": "P41", "barcode": "4012345678901", "uvp": 49.9, "size_run": ["S", "M"]}])
        self.assertIn("Incoterm FOB", r.payload["notes"]); self.assertIn("Lieferadresse Lager 1, Berlin", r.payload["notes"]); self.assertNotIn("shipAddress", r.payload)  # shipAddress laesst createOrder scheitern

    def test_ungueltiger_barcode_wird_nicht_uebernommen(self):
        self.assertTrue(core.valid_ean("4006381333931")); self.assertFalse(core.valid_ean("4012345678904")); self.assertFalse(core.valid_ean("12ab"))
        d = po(); d["items"][0]["product_info"] = {"barcode": "4012345678904", "uvp": 9.9}
        r = core.build(d, CTX, TODAY)
        self.assertIn("barcode_invalid", codes(r)); self.assertNotIn("barcode", r.product_specs[0]); self.assertIn("ungueltig", r.payload["notes"])

    def test_ein_cent_rundung_bei_summen_ist_ok(self):
        d = po(); d["items"][0]["variants"][0]["sizes"] = {"S": 3, "M": 3}; d["items"][0]["variants"][0]["price"] = 29572.625   # 6 Stk -> 177435.75
        r = core.build(d, CTX, TODAY); tot = r.payload["totalCost"]
        d["payments"] = [{"name": "70%", "status": "Unpaid", "amount": round(tot + 0.01, 2), "due": "2026-09-22"}]
        self.assertNotIn("payment_sum", codes(core.build(d, CTX, TODAY)))
        d["payments"][0]["amount"] = round(tot + 0.02, 2)
        self.assertIn("payment_sum", codes(core.build(d, CTX, TODAY)))

    def test_force_create_ueberstimmt_style_overlap(self):
        d = po(po_number="XW-NEU-9")   # gleicher Lieferant + gleicher Style XW-041 wie bestehende Order -> sonst BLOCK
        orders = CTX["orders"] + [{"id": "OX", "orderNumber": 99, "title": "PO-XW-ALT", "manufacturer": {"id": "V_XW"}, "totalCost": 1, "totalNumberOfPieces": 1,
                                   "items": [{"name": "XW-041 Men Windbreaker", "product": "P41"}]}]
        ctx = dict(CTX, orders=orders)
        self.assertEqual(core.build(d, ctx, TODAY).decision, "BLOCK")
        self.assertEqual(core.build(d, ctx, TODAY, force_create=True).decision, "CREATE")

    def test_po_nummer_die_anfang_einer_laengeren_ist_trifft_nicht(self):
        self.assertFalse(core.po_in_title("26071-DE-EA-2", "PO-LIEFERANT_W-26071-DE-EA-2EXTRA"))
        self.assertTrue(core.po_in_title("26071-DE-EA-2", "PO-LIEFERANT_W-26071-DE-EA-2"))
        self.assertTrue(core.po_in_title("26071-DE-EA-2", "PO-LIEFERANT_W-26071-DE-EA-2-RESERVE"))
        self.assertTrue(core.po_in_title("XW-SM260513", "PO-XW-SM260513"))
        self.assertFalse(core.po_in_title("AB", "PO-ABC"))

    def test_positionsname_enthaelt_die_stylenummer_einmal(self):
        self.assertEqual(core.item_display_name({"sku": "HY29583", "name": "MEN'S JACKET"}), "HY29583 MEN'S JACKET")
        self.assertEqual(core.item_display_name({"sku": "XW-041", "name": "XW-041 Men Windbreaker"}), "XW-041 Men Windbreaker")
        self.assertEqual(core.item_display_name({"sku": "AN-43", "name": ""}), "AN-43"); self.assertEqual(core.item_display_name({"sku": None, "name": "Nur Name"}), "Nur Name")
        self.assertEqual(core.item_display_name({}), "?")

    def test_bestell_kopf_in_den_notizen(self):
        d = po(doc_type="PI", doc_date="2026-10-02", incoterm="FOB", eta="2026-11-20", ship_to="Lager 1, Hamburg", notes="Besonderheit X")
        d["source"] = {"doc": "PI XW-SM260999.xlsx", "mail_id": "m1", "mail_date": "2026-10-14 09:30"}
        n = core.build(d, CTX, TODAY).payload["notes"]
        for part in ("Quelle: PI XW-SM260999, PI XW-SM260999.xlsx, Mail m1 (Mail vom 2026-10-14 09:30).", "PO-Datum 2026-10-02", "Incoterm FOB", "ETA 2026-11-20", "Lieferadresse Lager 1, Hamburg",
                     "Zahlungsbedingungen", "Besonderheit X"):
            self.assertIn(part, n)
        self.assertLess(n.index("Quelle:"), n.index("Besonderheit X"))   # Kopf zuerst, danach Dokument-Notizen

    def test_notizkopf_ohne_angaben_bleibt_schlank(self):
        d = po(); d["source"] = {"doc": "x", "mail_id": "m"}
        n = core.build(d, CTX, TODAY).payload["notes"]; self.assertNotIn("PO-Datum", n); self.assertNotIn("Incoterm", n)

    def test_fehlende_po_nr_aber_identische_order_ist_dublette_kein_blocker(self):
        d = po(po_number=None); r0 = core.build(d, CTX, TODAY)
        self.assertIn("po_number_missing", codes(r0))
        tot, pcs = r0.payload["totalCost"], r0.payload["totalNumberOfPieces"]
        ctx = dict(CTX, orders=CTX["orders"] + [{"id": "OT", "orderNumber": 77, "title": "PO-ANDERS-HEISST-ES", "manufacturer": {"id": "V_XW"}, "totalCost": tot, "totalNumberOfPieces": pcs}])
        r = core.build(d, ctx, TODAY)
        self.assertEqual(r.decision, "SKIP"); self.assertNotIn("po_number_missing", codes(r)); self.assertIn("po_number_missing_duplicate", codes(r))
        self.assertEqual(core.build(d, dict(CTX, orders=CTX["orders"]), TODAY).decision, "BLOCK")   # ohne Zwilling bleibt es ein Blocker

    def test_stylenummern_in_klammern_und_reine_zahlen_werden_erkannt(self):
        t = core.style_tokens("26498 Men Hoodie Regular (ALP-103, 65% Cotton)")
        self.assertIn("26498", t); self.assertIn("alp103", t)
        self.assertIn("hy29582", core.style_tokens("HY29582 KNITTED HALF-PLACKET 90% POLYESTER"))
        self.assertEqual(core.style_tokens("Men Hoodie 65% Cotton 320 GSM"), set())   # Prozent/GSM sind keine Styles
        self.assertTrue({"kcjk00027", "alp10326", "an43x"} >= {"kcjk00027", "alp10326"} and {"kcjk00027", "alp10326"} <= core.style_tokens("KC-JK-00027 Slim jacket (ALP-103-26)"))

    def test_titel_ohne_doppeltes_lieferantenkuerzel(self):
        self.assertEqual(core.make_title("LIEFERANT_D", "LIEFERANT_D-ALI20260821"), "PO-LIEFERANT_D-ALI20260821")
        self.assertEqual(core.make_title("Ningbo Lieferant D Co., Ltd", "LIEFERANT_D-T1"), "PO-LIEFERANT_D-T1")
        self.assertEqual(core.make_title("Lieferant A", "ALPHA-SWEAT-2026"), "PO-ALPHA-SWEAT-2026")
        self.assertEqual(core.make_title("Lieferant C", "SM260513"), "PO-LIEFERANT_C-SM260513")   # keine Verwechslung ohne gleiches Kuerzel

    def test_ohne_product_info_keine_specs(self):
        self.assertEqual(core.build(po(), CTX, TODAY).product_specs, [])


if __name__ == "__main__":
    unittest.main()
