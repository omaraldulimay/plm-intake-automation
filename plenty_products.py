#!/usr/bin/env python3
"""Plenty-BI-DB (nur lesend) -> Lifecycle PLM, pro Lieferant.

  .venv/bin/python plenty_products.py --supplier "lieferant_a"            # Report, schreibt nichts
  .venv/bin/python plenty_products.py --supplier "lieferant_a" --csv      # CSV der noch fehlenden Produkte -> output/review/
  .venv/bin/python plenty_products.py --supplier "lieferant_a" --fields   # Plan: Custom Fields fuer vorhandene Produkte
  .venv/bin/python plenty_products.py --supplier "lieferant_a" --fields --apply   # Custom Fields per REST schreiben

Ablauf: 1) --csv erzeugen, in der App per Import CSV hochladen (Chrome), 2) --fields --apply fuellt Plenty-ID, UVP, EK nach
(PUT ersetzt den ganzen customFields-Block, antwortet 500 und speichert trotzdem -> immer per Listen-GET pruefen).
Aktiv = Verkauf in den letzten --days Tagen (Standard 365)."""
import argparse, csv, datetime, json, os, re, subprocess
from collections import OrderedDict
from pathlib import Path

import plm_dima_sync as s
from plm_client import call

ROOT = Path(__file__).parent
DB = f"host=smilo-bi.cxar5ovsxcrg.eu-west-1.rds.amazonaws.com port=5432 dbname=postgres user=smilo_postgr sslmode=verify-full sslrootcert=db/global-bundle.pem"
KEYS = {"pid": "muxy47ha94z24q_plenty_produkt_id", "uvp": "muxy5365hi2xhz_uvp", "ek": "muxy5sc1s5a8yw_einkaufspreis"}
SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL", "5XL", "6XL"]
CATS = [("zip hoodie", "Hoodie"), ("hoodie", "Hoodie"), ("jogginghose", "Hose"), ("boxershorts", "Boxershorts"), ("shorts", "Shorts"),
        ("t-shirt", "T-Shirt"), ("poloshirt", "Poloshirt"), ("sweatshirt", "Herren Sweatshirts"), ("jacke", "Jacke"), ("socken", "Socken")]


def psql(sql):
    env = {**os.environ, "PGOPTIONS": "-c default_transaction_read_only=on", "PGCONNECT_TIMEOUT": "20"}
    out = subprocess.run(["psql", "-w", DB, "-At", "-F", "\t", "-c", sql], capture_output=True, text=True, env=env, check=True, cwd=ROOT).stdout
    return [r.split("\t") for r in out.splitlines()]


def load(supplier, days):
    sup = supplier.replace("'", "''")
    rows = psql(f"""select k.product_id, k.variation_no, k.variation_name, coalesce(k.attributes,''), coalesce(d.uvp::text,''), coalesce(d.purchase_price::text,''),
      coalesce((select max(w.week_start)::text from logistics.sku_sales_weekly w where w.ean=k.ean and w.instance_key=k.instance_key),'')
      from logistics.skus k left join logistics.sku_details d on d.ean=k.ean and d.instance_key=k.instance_key
      where k.instance_key=1 and k.supplier_name ilike '{sup}%' order by k.product_id, k.variation_no""")
    P = OrderedDict()
    for pid, vno, vname, attr, uvp, ek, last in rows:
        p = P.setdefault(pid, {"pid": pid, "vnos": [], "name": vname, "colors": [], "sizes": [], "uvp": [], "ek": [], "last": ""})
        p["vnos"].append(vno)
        m = dict(x.split(":", 1) for x in attr.split(", ") if ":" in x)
        if m.get("Color") and m["Color"] not in p["colors"]:
            p["colors"].append(m["Color"])
        if m.get("Size") and m["Size"] not in p["sizes"]:
            p["sizes"].append(m["Size"])
        if uvp:
            p["uvp"].append(float(uvp))
        if ek:
            p["ek"].append(float(ek))
        p["last"] = max(p["last"], last)
    cut = str(datetime.date.today() - datetime.timedelta(days=days))
    out = []
    for p in P.values():
        if p["last"] < cut:
            continue
        p["art"] = re.sub(r"-[A-Za-z]\d+$", "", p["vnos"][0])
        p["sizes"].sort(key=lambda z: SIZE_ORDER.index(z) if z in SIZE_ORDER else 99)
        p["cat"] = next((c for k, c in CATS if k in p["name"].lower()), "Other")
        p["uvp_v"] = max(p["uvp"]) if p["uvp"] else None
        p["ek_v"] = max(p["ek"]) if p["ek"] else None
        out.append(p)
    return out


def num(x):
    return f"{round(x, 2):g}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--supplier", required=True)
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--fields", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", help="kommagetrennte Artikelnummern begrenzen")
    a = ap.parse_args()
    prods = load(a.supplier, a.days)
    if a.only:
        want = {s.norm(x) for x in a.only.split(",")}
        prods = [p for p in prods if s.norm(p["art"]) in want]
    cur = s.products()
    idx = {}
    for x in cur.values():
        idx[s.norm(x["name"])] = x
        idx.setdefault(s.norm(x["sku"]), x)
    new = [p for p in prods if s.norm(p["art"]) not in idx]
    have = [(p, idx[s.norm(p["art"])]) for p in prods if s.norm(p["art"]) in idx]
    print(f"{a.supplier}: aktive Produkte {len(prods)} | neu (nicht im PLM) {len(new)} | schon im PLM {len(have)}")
    if a.csv:
        out = ROOT / f"output/review/plenty_{re.sub(r'[^a-z0-9]+', '_', a.supplier.lower())}_neu.csv"
        cols = ["Name", "Collection", "Category", "Status", "SKU", "Description", "Season", "Year", "Measurement Unit", "Sizes", "Variants", "Main Vendor", "Main Material", "Tags"]
        with out.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for p in new:
                w.writerow([p["art"], a.supplier.split()[0].title(), p["cat"], "", re.sub(r"[^A-Za-z0-9]", "", p["art"]).upper(), p["name"], "", "", "cm",
                            ", ".join(p["sizes"]), ", ".join(p["colors"]), "Lieferant A" if a.supplier.lower().startswith("alpha") else a.supplier, "", ""])
        print("CSV:", out)
    if a.fields:
        todo = []
        for p, x in have:
            want = {KEYS["pid"]: p["pid"]}
            if p["uvp_v"] is not None:
                want[KEYS["uvp"]] = num(p["uvp_v"])
            if p["ek_v"] is not None:
                want[KEYS["ek"]] = num(p["ek_v"])
            if (x.get("customFields") or {}) != want:
                todo.append((x, want))
        print(f"Custom Fields zu setzen: {len(todo)}")
        for x, want in todo[:50]:
            print(" ", x["sku"], json.dumps(want))
        if not a.apply:
            print("Trockenlauf (mit --apply schreiben).")
            return
        for x, want in todo:
            before = s.products()[x["id"]]
            st, res = call("PUT", f"products/{x['id']}", {"customFields": want, "expectedUpdatedAt": before["updatedAt"]})
            after = s.products()[x["id"]]
            ok = (after.get("customFields") or {}) == want
            diff = {k for k in set(before) | set(after) if k not in ("updatedAt", "customFields") and before.get(k) != after.get(k)}
            print(f"  {x['sku']}: HTTP {st} gespeichert={ok} fremde Aenderungen={sorted(diff) or 'keine'}")
            if diff or not ok:
                raise SystemExit("Abbruch: unerwartetes Ergebnis")


if __name__ == "__main__":
    main()
