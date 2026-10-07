#!/usr/bin/env python3
"""Zweistufiges Anlegen (Muster wie beim Vendor): POST nur mit einfachen Feldern, Listen danach per PUT + expectedUpdatedAt.

Hypothese (belegt durch Vendor-Verhalten): POST mit Listen (sizes, items, payments, contacts, addresses) -> 500,
POST mit nur einfachen Feldern -> 201, Listen kommen per PUT mit dem Versionsstand.

Es werden nur ECHTE, gewollte Datensaetze angelegt:
  1. Produkt SNW26-102 (fehlt im PLM)   2. PO "EasyFitness ALPHA MEN" (alle 5 Produkte existieren)
Schutz: Dublettencheck vor jedem POST, Pruefung per Listen-GET (Server antwortet oft 500, obwohl gespeichert),
Stopp bei jedem unklaren Ergebnis, alles steht in output/upload_log.jsonl.

  .venv/bin/python plm_try_create.py            # Trockenlauf
  .venv/bin/python plm_try_create.py --apply
"""
import json
import sys

import plm_create_orders as m
from plm_client import call

norm = m.norm
APPLY = "--apply" in sys.argv
short = lambda r: json.dumps(r, ensure_ascii=False)[:600]


def all_products():
    out, p = [], 1
    while True:
        st, d = call("GET", "products", limit=100, page=p)
        out += d["data"]
        if p >= d["pagination"]["pages"]:
            return out
        p += 1


def find_product(name):
    return next((x for x in all_products() if norm(x["name"]) == norm(name) or norm(x["sku"]) == norm(name)), None)


def find_order(title):
    return next((o for o in call("GET", "orders")[1] if o["title"] == title), None)


def try_posts(label, path, bodies, finder):
    """Erster Versuch, nach dem der Datensatz existiert, gewinnt."""
    for name, body in bodies:
        if finder():
            print(f"  [{label}] existiert bereits - kein weiterer POST.")
            return finder()
        print(f"  Versuch {name}: {short(body)[:160]}")
        if not APPLY:
            continue
        st, res = call("POST", path, body)
        print(f"    -> {st} {short(res)}")
        rec = finder()
        if rec:
            print(f"    ERFOLG (HTTP {st}) - Datensatz existiert jetzt.")
            return rec
    return finder() if APPLY else None


def step_product(sib):
    print("1) Produkt SNW26-102: Huelle existiert, jetzt sizes/variants per PUT fuellen")
    rec = find_product("SNW26-102")
    if not rec:
        print("  Produkt fehlt - Huelle zuerst anlegen (Vorversion des Skripts).")
        return
    S = ["XS", "S", "M", "L", "XL"]
    tries = [("sizes als Strings", {"sizes": S}),
             ("sizes als {title,position}", {"sizes": [{"title": x, "position": i} for i, x in enumerate(S)]}),
             ("variants=[Default Style]", {"variants": [{"name": "Default Style"}]}),
             ("variants=[{name,color}]", {"variants": [{"name": "Default Style", "color": {}}]})]
    for name, patch in tries:
        rec = find_product("SNW26-102")
        key = list(patch)[0]
        if rec[key] and (key != "variants" or len(rec["variants"]) > 0):
            print(f"  [{key}] schon gefuellt - uebersprungen")
            continue
        print(f"  Versuch {name}: {short(patch)[:150]}")
        if not APPLY:
            continue
        st, res = call("PUT", f"products/{rec['id']}", {**patch, "expectedUpdatedAt": rec["updatedAt"]})
        after = find_product("SNW26-102")
        ok = bool(after[key])
        print(f"    -> {st} {short(res)[:250]} | {key} jetzt: {short(after[key])[:160]} | {'ERFOLG' if ok else 'nicht gespeichert'}")


def step_order(vendor_id):
    print("\n2) PO EasyFitness ALPHA MEN: erst Huelle, dann items/payments per PUT")
    by = {}
    for x in all_products():
        by.setdefault(norm(x["name"]), []).append(x)
    body = m.build(m.load_pos()["ALPHA_MEN"], vendor_id, by)
    title = body["title"]
    draft = call("GET", "orders")[1][0]["status"]["id"]
    shells = [("H0 title+manufacturerId+items[]+payments[] (bewaehrt)", {"title": title, "manufacturerId": vendor_id, "items": [], "payments": []}),
              ("H1 title+manufacturer+items[]+payments[]", {"title": title, "manufacturer": vendor_id, "items": [], "payments": []}),
              ("H2 title+manufacturerId+items[]+payments[]", {"title": title, "manufacturerId": vendor_id, "items": [], "payments": []}),
              ("H3 H1 + currency USD", {"title": title, "manufacturer": vendor_id, "items": [], "payments": [], "currency": "USD"}),
              ("H4 H1 + statusId", {"title": title, "manufacturer": vendor_id, "items": [], "payments": [], "statusId": draft}),
              ("H5 title+manufacturer+status{id}", {"title": title, "manufacturer": vendor_id, "status": {"id": draft}}),
              ("H6 mit erster Position (Produkt-ID)", {"title": title, "manufacturer": vendor_id, "items": body["items"][:1], "payments": []})]
    rec = try_posts("PO", "orders", shells, lambda: find_order(title))
    if not APPLY:
        return
    if not rec:
        print("  PO-Huelle nicht angelegt - bitte Ausgabe an Claude.")
        return
    import copy
    def with_ids(items):  # Id-Muster der REST-API: productId statt product
        out = copy.deepcopy(items)
        for i in out:
            i["productId"] = i.pop("product")
        return out
    def refresh():
        return find_order(title)
    by_id = {x["id"]: x for x in all_products()}
    def full_items(product_as):  # Aufbau wie bei vorhandenen POs: name, product, variants[variantId,name,amounts[...]], Summen
        out = []
        for i in body["items"]:
            pid = i["product"]
            prod = by_id[pid]
            vs = []
            for v in i["variants"]:
                amts = [{"key": a["key"], "quantity": a["quantity"], "price": 0, "cost": 0, "shippedQuantity": 0,
                         "remainingQuantity": a["quantity"], "fulfillmentPercentage": 0, "totalValue": 0, "totalCost": 0} for a in v["amounts"]]
                vs.append({"variantId": v["variantId"], "name": v["name"], "color": None, "avatar": None, "amounts": amts,
                           "totalQuantity": i["totalQuantity"], "totalShippedQuantity": 0, "totalRemainingQuantity": i["totalQuantity"],
                           "fulfillmentPercentage": 0})
            out.append({"name": prod["name"], "product": pid if product_as == "str" else {"id": pid}, "variants": vs,
                        "price": None, "cost": 0, "unit": None, "totalValue": 0, "totalCost": 0, "totalQuantity": i["totalQuantity"],
                        "totalShippedQuantity": 0, "totalRemainingQuantity": i["totalQuantity"], "fulfillmentPercentage": 0})
        return out
    pay = lambda extra: [{"name": p_["name"], "terms": p_["terms"], "status": "Unpaid", **extra} for p_ in body["payments"]]
    steps = [("A1 payments mit amount=0, dueDate=null", lambda: {"payments": pay({"amount": 0, "dueDate": None})}),
             ("A2 payments mit amount=0 (ohne dueDate)", lambda: {"payments": pay({"amount": 0})}),
             ("E1 items volle GET-Form, product{id}", lambda: {"items": full_items("obj"), "totalNumberOfPieces": body["totalNumberOfPieces"], "totalCost": 0}),
             ("E2 items volle GET-Form, product als ID-String", lambda: {"items": full_items("str"), "totalNumberOfPieces": body["totalNumberOfPieces"], "totalCost": 0})]
    for name, mk in steps:
        o = refresh()
        key = list(mk())[0]
        if key == "payments" and len(o["payments"]) == len(body["payments"]):
            print(f"  [{name}] schon gefuellt"); continue
        if key == "items" and len(o["items"]) == len(body["items"]):
            print(f"  [{name}] schon gefuellt"); continue
        print(f"  Versuch {name}")
        st, res = call("PUT", f"orders/{o['id']}", {**mk(), "expectedUpdatedAt": o["updatedAt"]})
        a2 = refresh()
        print(f"    -> {st} {short(res)[:300]} | Positionen {len(a2['items'])}/5, Stueck {a2['totalNumberOfPieces']}, Payments {len(a2['payments'])}/4")
    o = refresh()
    print(f"  Endstand: Positionen {len(o['items'])}/5, Stueck {o['totalNumberOfPieces']} (Soll {body['totalNumberOfPieces']}), Payments {len(o['payments'])}/4, Vendor {o['manufacturer']['name']}, Status {o['status']['status']}")


def main():
    prods = all_products()
    sib = next(x for x in prods if x["name"] == "SNM26-002")
    vendor = next(v for v in call("GET", "vendors")[1] if v["name"] == "Lieferant A")
    step_product(sib)
    step_order(vendor["id"])


if __name__ == "__main__":
    main()
