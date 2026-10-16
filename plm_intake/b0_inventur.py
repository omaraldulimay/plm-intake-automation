"""B0 Inventur Phase 2 (NUR LESEN, schreibt nichts ins PLM).

  python3 -m plm_intake.b0_inventur            Bericht output/phase2/B0/inventur.md + inventur.json

Liest per REST Produkte/Bestellungen/Sendungen/Lieferanten und per Browser-GraphQL je Produkt: Verpackung, Maße (Basis), Techpack-Datensätze, Hauptmaterial, Identifier.
Zählt Lücken je Feld, listet Testobjekte (Löschliste für Omar) und die Produkte ohne Verpackung/Maße/Techpack/Hauptmaterial."""
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "phase2" / "B0"
CHUNK = 40
TEST_RX = re.compile(r"(?i)^(zz|t1-)|zz|neu aus mails|test")


def has_values(rows):
    """Messzeilen mit mindestens einem Wert > 0 ausser Toleranzen (Nullzeilen der Vorlage zaehlen nicht)."""
    for r in rows or []:
        for k, v in (r.get("metadata") or {}).items():
            if k.lower().startswith("tol"):
                continue
            try:
                if float(str(v).replace(",", ".")) > 0:
                    return True
            except ValueError:
                pass
    return False


def is_test(*vals):
    return any(TEST_RX.search(str(v or "")) for v in vals)


def retry_call(call):
    import time
    def f(*a, **k):
        for i in range(4):
            try:
                return call(*a, **k)
            except Exception:
                time.sleep(5 * (i + 1))
        return call(*a, **k)
    return f


def main(argv=None):
    import plm_client
    from plm_intake import batch_plan as bp
    from plm_intake.context import fetch_all
    OUT.mkdir(parents=True, exist_ok=True)
    products = fetch_all(retry_call(plm_client.call), "products")
    orders = fetch_all(retry_call(plm_client.call), "orders")
    shipments = fetch_all(retry_call(plm_client.call), "shipments")
    vendors = fetch_all(retry_call(plm_client.call), "vendors")
    real = [p for p in products if not is_test(p.get("sku"), p.get("name"))]
    det = {}
    ids = [p["id"] for p in real]
    bp.DETAIL_JS = bp.DETAIL_JS.replace("    ident:", "    meta: '{ productMeasurementMetadata(productId:$productId){ id metadata } }',\n    ident:")
    for i in range(0, len(ids), CHUNK):
        det.update(bp.fetch_details(ids[i:i + CHUNK]))
        print("Details %d/%d" % (min(i + CHUNK, len(ids)), len(ids)), flush=True)
    rows, cnt = [], Counter()
    for p in real:
        d = det.get(p["id"]) or {}
        inf = d.get("info") or {}
        pk = inf.get("packaging") or {}
        has = {
            "verpackung": any(pk.get(k) for k in ("cartonLengthCm", "cartonGrossWeightKg", "piecesPerCarton", "countryOfOrigin")),
            "hs": bool(pk.get("hsCode")),
            "masse": has_values(d.get("meta")),
            "material": bool(inf.get("mainMaterial")),
            "techpack_datensatz": any((t.get("name") or "") != "Default Techpack" for t in (d.get("tp") or [])),
            "ean": any(z.get("barcode") for v in (d.get("ident") or []) for z in (v.get("sizes") or [])),
            "fehler": bool([k for k in d if k.endswith("_err")]) or not d,
        }
        for k, v in has.items():
            cnt[k] += 1 if v else 0
        rows.append({"id": p["id"], "sku": p.get("sku"), "name": p.get("name"), "vendor": (p.get("mainManufacturer") or {}).get("name") if isinstance(p.get("mainManufacturer"), dict) else None,
                     "tags": p.get("tags"), **has})
    test_prod = [{"id": p["id"], "sku": p.get("sku"), "name": p.get("name")} for p in products if is_test(p.get("sku"), p.get("name"))]
    test_ord = [{"id": o["id"], "title": o.get("title")} for o in orders if is_test(o.get("title"))]
    test_shp = [{"id": s["id"], "title": s.get("title")} for s in shipments if is_test(s.get("title"))]
    test_ven = [{"id": v["id"], "name": v.get("name")} for v in vendors if is_test(v.get("name"))]
    ord_status = Counter(str((o.get("status") or {}).get("status") if isinstance(o.get("status"), dict) else o.get("status")) for o in orders)
    shp_status = Counter(str(s.get("status")) for s in shipments)
    n = len(rows)
    res = {"stand": dt.datetime.now().isoformat(timespec="minutes"), "produkte_gesamt": len(products), "produkte_echt": n, "orders": len(orders), "shipments": len(shipments), "vendors": len(vendors),
           "mit": dict(cnt), "ohne_verpackung": [r["sku"] for r in rows if not r["verpackung"]][:2000], "ohne_masse": [r["sku"] for r in rows if not r["masse"]],
           "ohne_material": [r["sku"] for r in rows if not r["material"]], "test": {"produkte": test_prod, "orders": test_ord, "sendungen": test_shp, "lieferanten": test_ven}, "rows": rows}
    (OUT / "inventur.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    L = ["# B0 Inventur (nur gelesen)", "", "Stand %s" % res["stand"], "",
         "- Produkte: %d gesamt, %d echt (ohne Testobjekte); Orders %d; Sendungen %d; Lieferanten %d" % (len(products), n, len(orders), len(shipments), len(vendors)),
         "- Order-Status: %s" % dict(ord_status), "- Sendungs-Status: %s" % dict(shp_status), "", "## Abdeckung je Feld (echte Produkte)", "", "| Feld | mit Wert | ohne |", "|---|---|---|"]
    for k in ("verpackung", "hs", "masse", "material", "techpack_datensatz", "ean"):
        L.append("| %s | %d | %d |" % (k, cnt[k], n - cnt[k]))
    L += ["", "Produkte mit Lesefehler: %d" % cnt["fehler"], "", "## Löschliste Testobjekte (Omar löscht)", "",
          "- Produkte (%d): %s" % (len(test_prod), ", ".join("%s" % t["sku"] for t in test_prod)),
          "- Orders (%d): %s" % (len(test_ord), ", ".join(str(t["title"]) for t in test_ord)),
          "- Sendungen (%d): %s" % (len(test_shp), ", ".join(str(t["title"]) for t in test_shp)),
          "- Lieferanten (%d): %s" % (len(test_ven), ", ".join(str(t["name"]) for t in test_ven)), "",
          "Details mit IDs: inventur.json"]
    (OUT / "inventur.md").write_text("\n".join(L))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
