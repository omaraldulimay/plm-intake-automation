import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import alias_learn, events, klaerbogen, klaerbogen_apply  # noqa: E402

V = [{"id": "VA", "name": "Lieferant A", "contacts": []}, {"id": "VW", "name": "Lieferant C", "contacts": []}]


def order(i, title, vid, pcs, status="In Production", item="X", variants=()):
    return {"id": i, "title": title, "poNumber": "", "orderNumber": int(i[1:]), "createdAt": "2026-05-01T00:00:00Z", "manufacturer": {"id": vid},
            "totalNumberOfPieces": pcs, "status": {"status": status},
            "items": [{"name": item, "product": {"id": "p" + i}, "variants": [{"name": v} for v in variants]}]}


O = [order("o1", "PO-ALPHA-KUNDE_X-LAGER", "VA", 1000, item="Jacke AL29008"), order("o2", "PO-ALPHA-KUNDE_X-CH", "VA", 2000, item="Hose AL30001"),
     order("o3", "PO-WONDERS-CHEETAH", "VW", 5000, variants=("Cheetah",)), order("o4", "PO-WONDERS-CROCO", "VW", 6000, variants=("Crocodile",))]
CTX = {"vendors": V, "products": [{"id": "po1", "sku": "AL29008"}], "orders": O, "aliases": {}}


def ev(summary, vendor="Lieferant A", typ="SHIPMENT", subj="Betreff eins zwei drei", mail="m1", **kw):
    e = {"type": typ, "vendor": vendor, "ref": {}, "summary": summary, "details": kw.pop("details", {}), "_mail": {"id": mail, "date": "2026-10-12 10:00", "subject": subj, "from": "x@y.z"}}
    e.update(kw)
    return e


def bogen(evs, rows=None):
    pl = events.plan(evs, O, V, {}, {}, vendor_only=True, products=CTX["products"])
    col = {"plan": pl, "events": evs, "rows": rows or [], "style_aliases": {}, "inbox": Path("/nonexistent")}
    return klaerbogen.build(col, CTX, Path("/nonexistent"))


class Kandidaten(unittest.TestCase):
    def test_nichts_spricht_keine_empfehlung_bei_vielen(self):
        b = bogen([ev("Etwas ist passiert")])
        c = b["faelle"][0]
        self.assertEqual(c["konfidenz"], "keine")
        self.assertTrue(all(k["score"] == 0 for k in c["kandidaten"]))   # nur Auswahl, kein Signal
        self.assertIn("kein Signal", klaerbogen.cand_cell(c, "a"))

    def test_menge_wirkt_wenn_eindeutig(self):
        # Menge steht NUR im Text, keine PO-Nr: find_order liefert 'menge' selbst -> kein offener Fall
        b = bogen([ev("Lieferung von 2.000 Stk", typ="SCHEDULE")])
        self.assertEqual(b["faelle"], [])

    def test_unterscheidendes_wort_variante(self):
        b = bogen([ev("Barcode fuer Cheetah Druck bestaetigt", vendor="Lieferant C", typ="OTHER", ref={"po_number": "XW-042"})])
        c = b["faelle"][0]
        self.assertEqual(c["kandidaten"][0]["order"]["id"], "o3")
        self.assertIn("cheetah", c["kandidaten"][0]["begruendung"][0])
        self.assertIn(c["konfidenz"], ("mittel", "hoch"))

    def test_ohne_lieferant_nur_starke_signale(self):
        b = bogen([ev("Cheetah Muster", vendor=None, typ="SAMPLE")])
        for c in b["faelle"]:
            self.assertEqual(c["kandidaten"], [])   # Variantenwort zaehlt ohne Lieferant nicht
            self.assertEqual(c["konfidenz"], "keine")

    def test_gruppierung_je_mail(self):
        b = bogen([ev("Aktion A"), ev("Aktion B"), ev("Aktion C", mail="m2")])
        self.assertEqual(sorted(len(c["ereignisse"]) for c in b["faelle"]), [1, 2])
        self.assertEqual([c["nr"] for c in b["faelle"]], ["F01", "F02"])

    def test_pool_aus_grund_mehrdeutig(self):
        pool, named = klaerbogen.pool_from_reason("mehrdeutig: PO-WONDERS-CHEETAH, PO-WONDERS-CROCO", V[1], O)
        self.assertTrue(named)
        self.assertEqual({o["id"] for o in pool}, {"o3", "o4"})
        pool, named = klaerbogen.pool_from_reason("mehrdeutig: 2 laufende Orders von Lieferant A", V[0], O)
        self.assertFalse(named)
        self.assertEqual({o["id"] for o in pool}, {"o1", "o2"})

    def test_complete_und_testorders_nie_kandidat(self):
        o = O + [order("o9", "PO-ALPHA-DONE", "VA", 10, status="Complete")]
        self.assertNotIn("o9", {x["id"] for x in klaerbogen.pool_for(V[0], o)})

    def test_markdown_ohne_pipes_im_text(self):
        b = bogen([ev("Text | mit Pipe")])
        md = klaerbogen.render_md(b)
        row = [l for l in md.splitlines() if l.startswith("| F01")][0]
        self.assertEqual(row.count("|"), 10)


class Einlesen(unittest.TestCase):
    def setUp(self):
        self.b = bogen([ev("Container MSKU1234567 entladen", details={"container": "MSKU1234567"}), ev("Zoll Hamburg", mail="m2")])

    def md(self, wahl):
        md = klaerbogen.render_md(self.b).splitlines()
        out = []
        for l in md:
            for nr, w in wahl.items():
                if l.startswith("| %s " % nr):
                    l = l[:-2] + " %s |" % w
            out.append(l)
        return "\n".join(out)

    def test_parse_md_und_gen(self):
        ch, gen = klaerbogen_apply.parse_md(self.md({"F01": "a", "F02": "info"}))
        self.assertEqual((ch["F01"], ch["F02"], gen), ("a", "info", self.b["gen_id"]))

    def test_offen_bleibt_offen(self):
        ch, _ = klaerbogen_apply.parse_md(self.md({}))
        p = klaerbogen_apply.plan(self.b, ch, {}, {}, {})
        self.assertEqual((p["zeilen"], p["ev_ov"]), ([], {}))

    def test_wahl_schreibt_override_und_lernt_alias(self):
        ch, _ = klaerbogen_apply.parse_md(self.md({"F01": "a", "F02": "info"}))
        p = klaerbogen_apply.plan(self.b, ch, {}, {}, {})
        m1 = self.b["faelle"][0]["ereignisse"][0]["marker"]
        m2 = self.b["faelle"][1]["ereignisse"][0]["marker"]
        a_id = self.b["faelle"][0]["kandidaten"][0]["order"]["id"]
        self.assertEqual(p["ev_ov"], {m1: a_id, m2: events.INFO_OVERRIDE})
        self.assertEqual(p["aliases"], {"MSKU1234567": a_id})   # Container eindeutig -> Alias; nur beim Order-Fall, nicht bei info

    def test_freitext_po_id_nummer_titel(self):
        for w in ("PO26-002", "#2", "PO-ALPHA-KUNDE_X-CH", "o2"):
            self.assertEqual(klaerbogen_apply.resolve_order(w, self.b), "o2", w)
        self.assertIsNone(klaerbogen_apply.resolve_order("PO26-999", self.b))

    def test_unbekannte_wahl_ist_fehler(self):
        p = klaerbogen_apply.plan(self.b, {"F01": "xyz"}, {}, {}, {})
        self.assertTrue(p["fehler"] and p["ev_ov"] == {})

    def test_abweichender_bestand_nur_mit_overwrite(self):
        m1 = self.b["faelle"][0]["ereignisse"][0]["marker"]
        b_id = self.b["faelle"][0]["kandidaten"][1]["order"]["id"]
        p = klaerbogen_apply.plan(self.b, {"F01": "a"}, {m1: b_id}, {}, {})
        self.assertEqual(p["ev_ov"][m1], b_id); self.assertTrue(p["uebersprungen"])
        p = klaerbogen_apply.plan(self.b, {"F01": "a"}, {m1: b_id}, {}, {}, overwrite=True)
        self.assertNotEqual(p["ev_ov"][m1], b_id)

    def test_alias_konflikt_wird_mehrdeutig(self):
        a_id = self.b["faelle"][0]["kandidaten"][0]["order"]["id"]
        other = next(i for i in ("o1", "o2") if i != a_id)
        p = klaerbogen_apply.plan(self.b, {"F01": "a"}, {}, {"MSKU1234567": other}, {})
        self.assertEqual(p["aliases"]["MSKU1234567"], alias_learn.AMBIG)
        self.assertTrue(p["konflikte"])

    def test_override_wirkt_im_plan(self):   # Kreislauf: gewaehlter Marker -> naechster Plan ordnet stark zu
        ch = {"F01": "a"}
        p = klaerbogen_apply.plan(self.b, ch, {}, {}, {})
        pl = events.plan([ev("Container MSKU1234567 entladen", details={"container": "MSKU1234567"})], O, V, {}, {}, vendor_only=True, products=CTX["products"], event_overrides=p["ev_ov"])
        self.assertEqual(pl["unmatched"], [])

    def test_beleg_skip_create_und_alias(self):
        rows = [{"file": "d1.json", "kind": "ORPHAN_DOC", "po": "6300"}]
        b = self.b
        b["faelle"].append({"art": "beleg", "nr": "B01", "vendor": "X", "konfidenz": "keine", "datei": "d1.json", "kind": "ORPHAN_DOC", "keys": ["INV-2275-EXP"], "kandidaten": [], "datum": "", "betreff": "", "beleg": "", "grund": ""})
        b["faelle"].append({"art": "beleg", "nr": "B02", "vendor": "X", "konfidenz": "keine", "datei": "d2.json", "kind": "AMBIGUOUS_DOC", "keys": ["INV-77-ABC"],
                            "kandidaten": [{"key": "a", "order": b["orders"]["o1"], "score": 0, "begruendung": []}], "datum": "", "betreff": "", "beleg": "", "grund": ""})
        p = klaerbogen_apply.plan(b, {"B01": "skip", "B02": "a"}, {}, {}, {})
        self.assertEqual(p["overrides"], {"d1.json": "SKIP"})
        self.assertEqual(p["aliases"], {"INV-77-ABC": "o1"})
        self.assertTrue(rows)


if __name__ == "__main__":
    unittest.main()
