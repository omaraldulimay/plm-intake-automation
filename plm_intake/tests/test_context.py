import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plm_intake import core  # noqa: E402
from plm_intake.context import fetch_all  # noqa: E402
from plm_intake.tests.test_core import VENDORS  # noqa: E402


def fake(rows, mode, page_size=20):
    """mode: 'dict' ({data,pagination}), 'list' (nackte Liste, seitenweise ohne Metadaten), 'all' (ignoriert page/limit)"""
    calls = []

    def call(method, path, **kw):
        calls.append(kw)
        page, limit = kw.get("page", 1), min(kw.get("limit", 20), page_size)
        if mode == "all":
            return 200, list(rows)
        chunk = rows[(page - 1) * limit: page * limit]
        if mode == "list":
            return 200, chunk
        return 200, {"data": chunk, "pagination": {"page": page, "limit": limit, "total": len(rows), "pages": max(1, -(-len(rows) // limit))}}
    call.calls = calls
    return call


class Paging(unittest.TestCase):
    rows = [{"id": str(i)} for i in range(53)]

    def test_alle_modi_liefern_alles_ohne_doppelte(self):
        for mode in ("dict", "list", "all"):
            got = fetch_all(fake(self.rows, mode), "x", limit=20)
            self.assertEqual(len(got), 53, mode)
            self.assertEqual(len({g["id"] for g in got}), 53, mode)

    def test_genau_volle_letzte_seite(self):
        rows = [{"id": str(i)} for i in range(40)]
        self.assertEqual(len(fetch_all(fake(rows, "list"), "x", limit=20)), 40)

    def test_leere_liste(self):
        for mode in ("dict", "list", "all"):
            self.assertEqual(fetch_all(fake([], mode), "x"), [])

    def test_http_fehler_bricht_ab(self):
        with self.assertRaises(RuntimeError):
            fetch_all(lambda m, p, **kw: (500, "boom"), "x")

    def test_endlosschleife_wird_verhindert(self):
        n = [0]

        def call(m, p, **kw):
            n[0] += 1
            return 200, [{"id": "n%d" % n[0]}] * 100   # liefert immer 'neue' ids, volle Seiten
        with self.assertRaises(RuntimeError):
            fetch_all(call, "x", limit=100, max_pages=5)


class VendorNamen(unittest.TestCase):
    V = VENDORS + [{"id": "V_WS", "name": "LIEFERANT_Y LIMITED"}, {"id": "V_KC", "name": "LIEFERANT_V LIMITED"},
                   {"id": "V_KH", "name": "LIEFERANT_W CO., LTD"}, {"id": "V_JO", "name": "LIEFERANT_X INDUSTRY CO.,LTD"}]

    def test_kurznamen_aus_dem_register(self):
        for src, vid in [("LIEFERANT_Y", "V_WS"), ("LIEFERANT_V", "V_KC"), ("LIEFERANT_W", "V_KH"), ("CHINA LIEFERANT_X", "V_JO"), ("LIEFERANT_D", "V_LIEFERANT_D"), ("LIEFERANT_AA", "V_LIEFERANT_AA")]:
            v, _ = core.match_vendor(src, self.V)
            self.assertEqual(v and v["id"], vid, src)

    def test_alias_hat_vorrang_und_greift_bei_tippfehlern(self):
        v, why = core.match_vendor("MUICHES", self.V)
        self.assertIsNone(v)
        v, why = core.match_vendor("MUICHES", self.V, {"MUICHES": "Xiamen Lieferant G Industry Co., Ltd"})
        self.assertEqual((v["id"], why), ("V_MIU", "alias"))

    def test_alias_auf_unbekannten_vendor_wird_ignoriert(self):
        v, _ = core.match_vendor("Foo", self.V, {"Foo": "Gibt es nicht"})
        self.assertIsNone(v)

    def test_zu_kurz_oder_allgemein_kein_treffer(self):
        for n in ["Sport", "XW", "Textile", "Ltd", ""]:
            self.assertIsNone(core.match_vendor(n, self.V)[0], n)


if __name__ == "__main__":
    unittest.main()
