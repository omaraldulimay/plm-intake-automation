"""Gesamtpruefung EAN/SKU im PLM gegen Plenty (nur lesen): steht jede EAN an der Zelle (Farbe x Groesse), zu der sie in Plenty gehoert?

  python3 -m plm_intake.ean_audit [--fix-plan]     Bericht output/barcodes/audit_<Zeit>.md (+ fix_plan.json mit den falsch belegten Zellen)
Befund-Arten: FALSCH = EAN gehoert laut Plenty zu anderer Farbe/Groesse; SKU_ANDERS = SKU weicht von der Plenty-Variantennummer ab; UNBEKANNT = EAN nicht in Plenty (andere Quelle, nicht bewertet)."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import barcodes as bc, core  # noqa: E402


def audit(prods, ident, prows):
    findings, stats = [], {"zellen": 0, "ok": 0, "falsch": 0, "sku_anders": 0, "unbekannt": 0}
    for p in prods:
        rows = prows.get(core.norm(p.get("sku")), [])
        by_ean = {r["ean"]: r for r in rows if r["ean"]}
        for c in bc.cells_of(ident.get(p["id"])):
            if not c["barcode"]:
                continue
            stats["zellen"] += 1
            r = by_ean.get(c["barcode"])
            if not r:
                stats["unbekannt"] += 1; continue
            ck = {bc.colour_key(c["variant"]), bc.colour_key(c["color"])} - {("?", "", ())}
            same = bc.colour_key(r["color"]) in ck and bc.norm_size(r["size"]) == bc.norm_size(c["size"])
            if not same:
                stats["falsch"] += 1
                findings.append({"sku": p.get("sku"), "pid": p["id"], "iid": c["iid"], "sid": c["sid"], "variant": c["variant"], "size": c["size"], "plenty_color": r["color"], "plenty_size": r["size"], "ean": c["barcode"], "plm_sku": c["sku"], "plenty_vn": r["variation_no"]})
            elif c["sku"] and c["sku"] != r["variation_no"]:
                stats["sku_anders"] += 1
            else:
                stats["ok"] += 1
    return findings, stats


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    products = fetch_all(plm_client.call, "products")
    prods = bc.real_products(products)[:a.n]
    ident = bc.run_js(bc.READ_JS.replace("__IDS__", json.dumps([p["id"] for p in prods])))
    prows = bc.plenty_rows([p.get("sku") for p in prods])
    findings, stats = audit(prods, ident, prows)
    out = ROOT / "output" / "barcodes"; out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    rep = ["# EAN-Gesamtpruefung %s" % stamp, "", "Zellen mit EAN: %(zellen)d | passt: %(ok)d | FALSCH: %(falsch)d | SKU weicht ab: %(sku_anders)d | EAN nicht in Plenty: %(unbekannt)d" % stats, ""]
    byp = {}
    for f in findings:
        byp.setdefault(f["sku"], []).append(f)
    for sku, fs in byp.items():
        rep.append("## %s: %d falsch belegt" % (sku, len(fs)))
        rep += ["- %s %s hat EAN %s, laut Plenty (%s) gehoert sie zu %s / %s" % (f["variant"], f["size"], f["ean"], f["plenty_vn"], f["plenty_color"], f["plenty_size"]) for f in fs[:6]]
    (out / ("audit_%s.md" % stamp)).write_text("\n".join(rep))
    (out / "fix_plan.json").write_text(json.dumps(findings, ensure_ascii=False, indent=1))
    print("\n".join(rep[:60]))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
