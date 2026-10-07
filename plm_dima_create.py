#!/usr/bin/env python3
"""Legt fehlende Alpha-Styles (AL29xxx aus Dima) im PLM an. Bekanntes Schreibformat (Befund 2026-10-07):
POST /products funktioniert NUR minimal (name, sku, description, categoryId, collectionId) -> 201;
mit sizes/additionalFields/guid kommt 500. Sizes/Varianten per PUT werden bisher nicht uebernommen.
Dieses Skript legt zuerst nur --first (AL29008) an und probiert dabei, ob 'variants' ohne sizes im POST greift.
  .venv/bin/python plm_dima_create.py            # Trockenlauf
  .venv/bin/python plm_dima_create.py --apply --first
  .venv/bin/python plm_dima_create.py --apply    # alle fehlenden (ausser Sweatshirt: keine Kategorie)"""
import json, sys
import plm_dima_sync as s
from plm_client import call

APPLY, FIRST = "--apply" in sys.argv, "--first" in sys.argv
COLLECTION_ALPHA = "6a8db7c73dc6b5b720f52cbc"
CAT = {"Hoodie": "6a8db7cc3dc6b5b720f52ce3", "Jogginghose": "6a8dba0c3dc6b5b720f563b0", "T-Shirt": "6a8dbe0e3dc6b5b720f65ee3"}  # Alpha-Kategorien der Styles AL29001-007


def main():
    cur = s.products()
    have = {s.norm(p["name"]) for p in cur.values()} | {s.norm(p["sku"]) for p in cur.values()}
    alpha = s.vendor_id(s.ALPHA_VENDOR)
    todo = [d for d in s.dima_styles() if s.norm(d["art"]) not in have]
    todo = [d for d in todo if d["type"] in CAT]
    print(f"fehlend und anlegbar: {len(todo)} (ohne Kategorie uebersprungen: Sweatshirt)")
    if FIRST:
        todo = todo[:1]
    for d in todo:
        body = {"name": d["art"].replace("AL", "AL", 1), "sku": d["art"], "categoryId": CAT[d["type"]], "collectionId": COLLECTION_ALPHA,
                "description": f"{d['dept']} {d['type']} {d['material']}, {d['weight_g']} g/m2"}
        print(d["art"], json.dumps(body, ensure_ascii=False))
        if not APPLY:
            continue
        ladder = [("minimal", body)]
        if FIRST:
            ladder.insert(0, ("minimal+variants", {**body, "variants": [{"name": d["colors"][0], "color": {"name": d["colors"][0]}}]}))
        for label, b in ladder:
            st, res = call("POST", "products", b)
            made = next((p for p in s.products().values() if s.norm(p["sku"]) == s.norm(d["art"])), None)
            print(f"  {label}: HTTP {st}, im PLM={bool(made)}, Varianten={[v['name'] for v in made['variants']] if made else None}")
            if made:
                st, _ = call("PUT", f"products/{made['id']}", {"mainManufacturer": alpha, "expectedUpdatedAt": made["updatedAt"]})
                after = s.products()[made["id"]]
                print(f"  Hersteller gesetzt={((after.get('mainManufacturer') or {}).get('id') == alpha)} (HTTP {st})")
                break
        else:
            sys.exit("nichts angelegt -> Abbruch")


if __name__ == "__main__":
    main()
