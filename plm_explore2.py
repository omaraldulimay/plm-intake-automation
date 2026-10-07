#!/usr/bin/env python3
"""Diagnose: scheitern die PO-Positionen (PUT items -> 500) an Groessen, die das Produkt nicht hat?

Test an der vorhandenen Draft-PO-Huelle "EasyFitness ALPHA MEN": Positionen werden nur mit Groessen gefuellt,
die das jeweilige Produkt im PLM bereits besitzt. Das ist reversibel (ein spaeterer PUT ersetzt die Positionen).
Ergebnis steht in output/explore2_report.json.

  .venv/bin/python plm_explore2.py --apply
"""
import json
import secrets
import sys
import time
from pathlib import Path

import plm_create_orders as m
from plm_client import call

ROOT = Path(__file__).parent
APPLY = "--apply" in sys.argv
norm = m.norm
oid = lambda: secrets.token_hex(12)


def products():
    out, p = [], 1
    while True:
        st, d = call("GET", "products", limit=100, page=p)
        out += d["data"]
        if p >= d["pagination"]["pages"]:
            return out
        p += 1


def main():
    report = {"attempts": [], "success": None}
    vendor = next(v for v in call("GET", "vendors")[1] if v["name"] == "Lieferant A")
    prods = products()
    by_id = {x["id"]: x for x in prods}
    by = {}
    for x in prods:
        by.setdefault(norm(x["name"]), []).append(x)
    body = m.build(m.load_pos()["ALPHA_MEN"], vendor["id"], by)
    title = body["title"]
    order = lambda: next((o for o in call("GET", "orders")[1] if o["title"] == title), None)

    dropped = []
    def build_items(prod_form, shape, ids):
        out = []
        for i in body["items"]:
            prod = by_id[i["product"]]
            have = set(prod["sizes"])
            vs = []
            for v in i["variants"]:
                keep = [a for a in v["amounts"] if a["key"] in have]
                dropped.extend((prod["name"], a["key"], a["quantity"]) for a in v["amounts"] if a["key"] not in have)
                amts = [({"key": a["key"], "quantity": a["quantity"], "price": 0, "cost": 0, "shippedQuantity": 0, "remainingQuantity": a["quantity"],
                          "fulfillmentPercentage": 0, "totalValue": 0, "totalCost": 0} if shape == "full" else {"key": a["key"], "quantity": a["quantity"]}) for a in keep]
                vd = {"variantId": v["variantId"], "name": v["name"], "amounts": amts}
                if ids: vd["id"] = oid()
                vs.append(vd)
            q = sum(a["quantity"] for v in vs for a in v["amounts"])
            d = {"name": prod["name"], "variants": vs, "totalQuantity": q, "cost": 0}
            d["product"] = i["product"] if prod_form == "str" else {"id": i["product"]}
            if ids: d["id"] = oid()
            out.append(d)
        return out

    combos = [(pf, sh, ids) for sh in ("full", "min") for pf in ("str", "obj") for ids in (False, True)]
    print(f"Diagnose: {len(combos)} Versuche (Positionen nur mit vorhandenen Groessen)")
    if not APPLY:
        return
    for pf, sh, ids in combos:
        dropped.clear()
        items = build_items(pf, sh, ids)
        o = order()
        st, res = call("PUT", f"orders/{o['id']}", {"items": items, "expectedUpdatedAt": o["updatedAt"]})
        after = order()
        ok = len(after["items"]) == len(items)
        name = f"product={pf} shape={sh} ids={ids}"
        report["attempts"].append({"name": name, "status": st, "ok": ok, "message": str(res)[:160] if isinstance(res, (str, dict)) else ""})
        print(f"  {'OK ' if ok else '-- '} {name} -> {st}")
        if ok:
            report["success"] = name
            report["pieces_in_po"] = after["totalNumberOfPieces"]
            report["dropped_sizes"] = [list(x) for x in dict.fromkeys(map(tuple, dropped))]
            report["working_item_example"] = json.dumps(items[0], ensure_ascii=False)[:900]
            break
        time.sleep(0.2)
    (ROOT / "output" / "explore2_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print("Ergebnis:", "Hypothese bestaetigt" if report["success"] else "Hypothese NICHT bestaetigt", "-> output/explore2_report.json")


if __name__ == "__main__":
    main()
