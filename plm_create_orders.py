#!/usr/bin/env python3
"""Legt POs aus output/po/*.json im PLM an (POST /orders), Status Draft, Preise/Betraege leer.

  .venv/bin/python plm_create_orders.py                  # Trockenlauf: zeigt Body + Vorabchecks (nur GET)
  .venv/bin/python plm_create_orders.py ALPHA_MEN --apply   # genau diese PO anlegen + per GET verifizieren

Schutz: Dublettencheck ueber den PO-Titel, jedes Produkt muss eindeutig im PLM gefunden werden
(sonst Abbruch statt Raten), nach dem POST wird per GET Menge fuer Menge gegengeprueft.
"""
import glob
import json
import re
import sys
from pathlib import Path

from plm_client import call

ROOT = Path(__file__).parent
norm = lambda s: re.sub(r"[^A-Z0-9]", "", str(s or "").upper())
# Bekannte Sonderfaelle: PO-Ref -> Produktname im PLM (siehe Korrekturliste)
ALIAS = {"SNM26-004": "SNM26-00"}  # abgeschnittener Name im PLM
VENDOR_NAME = "Lieferant A"
TRIGGER_NAME = {"before_production": "Deposit before production", "at_shipment": "At shipment",
                "after_shipment": "after shipment"}


def load_pos():
    return {Path(f).stem.split("__")[-1]: json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "output/po/*.json")))}


def resolve(it, by_name):
    for key in (ALIAS.get(it["supplier_ref"]["value"]), it["supplier_ref"]["value"], it["style_no"]["value"]):
        if key and norm(key) in by_name:
            hits = by_name[norm(key)]
            if len(hits) == 1:
                return hits[0]
            raise SystemExit(f"Abbruch: '{key}' ist im PLM nicht eindeutig ({len(hits)} Treffer)")
    raise SystemExit(f"Abbruch: Style {it['style_no']['value']} / {it['supplier_ref']['value']} nicht im PLM - erst Produkt anlegen")


def build(d, vendor_id, by_name):
    po = d["purchase_order"]["po_number"]
    base = re.sub(r"[^A-Z0-9]+", "-", (po.get("raw") or d["source_sheet"]).upper()).strip("-")
    multi = len(glob.glob(str(ROOT / "output/po" / f"{Path(d['source_file']).stem}__*.json"))) > 1
    title = f"PO-ALPHA-{base}" + (f"-{re.sub(r'[^A-Z0-9]+', '', d['source_sheet'].upper())}" if multi else "")
    items = []
    for it in d["items"]:
        p = resolve(it, by_name)
        variants = []
        for v in it["variants"]:
            pv = p["variants"][0] if len(p["variants"]) == 1 else next((x for x in p["variants"] if norm(x["name"]) == norm(v["colour"]["value"])), None)
            if pv is None:
                raise SystemExit(f"Abbruch: Variante {v['colour']['value']} bei {p['name']} nicht eindeutig")
            amounts = [{"key": s_, "quantity": int(q), "price": 0, "cost": 0} for s_, q in v["sizes"].items() if q]
            variants.append({"variantId": pv["id"], "name": pv["name"], "amounts": amounts})
        qty = sum(a["quantity"] for v in variants for a in v["amounts"])
        # Aufbau laut App-Code (order.utils): product = ID-String, Mengen/Kosten je Position
        items.append({"product": p["id"], "variants": variants, "totalQuantity": qty, "cost": 0})
    payments = []
    for m in d["terms"]["payment_milestones"]["value"]:
        name = f"{m['percent']:g}% " + (f"{m['days']} days {TRIGGER_NAME['after_shipment']}" if m["trigger"] == "after_shipment" else TRIGGER_NAME.get(m["trigger"], m["text"]))
        payments.append({"name": name, "terms": f"{m['percent']:g}% {m['text'].strip()}", "status": "Unpaid"})
    return {"title": title, "manufacturer": vendor_id, "items": items, "payments": payments,
            "totalCost": 0, "totalNumberOfPieces": sum(i["totalQuantity"] for i in items)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    pos = load_pos()
    sel = args or list(pos)
    st, vendors = call("GET", "vendors")
    vendor = next(v for v in vendors if v["name"] == VENDOR_NAME)
    prods, p = [], 1
    while True:
        st, dd = call("GET", "products", limit=100, page=p)
        prods += dd["data"]
        if p >= dd["pagination"]["pages"]:
            break
        p += 1
    by_name = {}
    for x in prods:
        by_name.setdefault(norm(x["name"]), []).append(x)
    st, orders = call("GET", "orders")
    existing = {o["title"]: o for o in orders}

    for key in sel:
        d = pos[key]
        body = build(d, vendor["id"], by_name)
        if body["title"] in existing:
            print(f"{key}: PO '{body['title']}' existiert schon - uebersprungen (Dublettenschutz)")
            continue
        pieces = body["totalNumberOfPieces"]
        print(f"\n{key}: {body['title']} | {len(body['items'])} Positionen | {pieces} Stk | {len(body['payments'])} Payments | Vendor {vendor['name']}")
        for i, it in zip(body["items"], d["items"]):
            print(f"   {it['style_no']['value']:10s} -> Produkt {i['product']} | {i['totalQuantity']} Stk")
        if not apply:
            print("   (Trockenlauf)")
            continue
        st, res = call("POST", "orders", body)
        print(f"   POST /orders -> {st}")
        if st not in (200, 201):
            print("   ", json.dumps(res, ensure_ascii=False)[:900])
            sys.exit(1)
        st, orders2 = call("GET", "orders")
        o = next((x for x in orders2 if x["title"] == body["title"]), None)
        if not o:
            print("   WARNUNG: PO nach dem Anlegen per GET nicht gefunden")
            sys.exit(1)
        got = {(it["product"]["id"]): it["totalQuantity"] for it in o["items"]}
        want = {i["product"]: i["totalQuantity"] for i in body["items"]}
        print(f"   Verifikation: Status={o['status']['status']}, Vendor={o['manufacturer']['name']}, Stueck {o['totalNumberOfPieces']} (Soll {pieces}), Payments {len(o['payments'])}")
        bad = {k: (want[k], got.get(k)) for k in want if want[k] != got.get(k)}
        print("   Mengen je Position:", "alle korrekt" if not bad else f"ABWEICHUNG {bad}")


if __name__ == "__main__":
    main()
