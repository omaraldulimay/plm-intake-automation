"""Falsch belegte EAN/SKU-Zellen korrigieren (aus output/barcodes/fix_plan.json der Gesamtpruefung ean_audit).

  python3 -m plm_intake.ean_fix            TROCKENLAUF: zeigt je falscher Zelle den richtigen Wert aus Plenty
  python3 -m plm_intake.ean_fix --apply    ueberschreibt NUR diese Zellen (overwriteExisting) mit den Plenty-Werten ihrer Farbe/Groesse und liest zurueck
Gibt es fuer die Zelle keinen Plenty-Wert, wird sie nicht angefasst (Mensch). Danach: ean_audit erneut, dann barcodes --apply fuer die freigewordenen EANs."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import barcodes as bc, core  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    fixes = json.load(open(ROOT / "output" / "barcodes" / "fix_plan.json"))
    import plm_client
    from plm_intake.context import fetch_all
    prods = {p["id"]: p for p in fetch_all(plm_client.call, "products")}
    skus = sorted({prods[f["pid"]]["sku"] for f in fixes})
    prows = bc.plenty_rows(skus)
    jobs, rep = {}, []
    for f in fixes:
        sku = prods[f["pid"]]["sku"]
        want = [r for r in prows.get(core.norm(sku), []) if bc.colour_key(r["color"]) in {bc.colour_key(f["variant"])} and bc.norm_size(r["size"]) == bc.norm_size(f["size"])]
        if len(want) != 1 or not bc.ean_ok(want[0]["ean"]):
            rep.append("- %s %s %s: kein eindeutiger Plenty-Wert (%d Treffer) -> Mensch" % (sku, f["variant"], f["size"], len(want))); continue
        w = want[0]
        rep.append("- %s %s %s: EAN %s/SKU %s -> %s/%s" % (sku, f["variant"], f["size"], f["ean"], f["plm_sku"], w["ean"], w["variation_no"]))
        jobs.setdefault(f["pid"], {"id": f["pid"], "sku": sku, "rows": []})["rows"].append({"identifierId": f["iid"], "sizeId": f["sid"], "barcode": w["ean"], "sku": w["variation_no"]})
    print("\n".join(rep))
    if a.apply and jobs:
        res = bc.run_js(bc.WRITE_JS.replace("__JOBS__", json.dumps(list(jobs.values()))).replace("__OVERWRITE__", "true"))
        print(json.dumps([{k: r.get(k) for k in ("sku", "res", "err", "fatal")} for r in res], ensure_ascii=False))
        after = bc.run_js(bc.READ_JS.replace("__IDS__", json.dumps(list(jobs))))
        bad = []
        for j in jobs.values():
            now = {(c["iid"], c["sid"]): c for c in bc.cells_of(after.get(j["id"]))}
            for r in j["rows"]:
                c = now.get((r["identifierId"], r["sizeId"]))
                if not c or c["barcode"] != r["barcode"] or c["sku"] != r["sku"]:
                    bad.append((j["sku"], r))
        print("Rueckpruefung:", "ALLES zurueckgelesen und gleich" if not bad else "ABWEICHUNG %s" % bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
