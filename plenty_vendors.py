#!/usr/bin/env python3
"""Legt Lieferanten aus der Plenty-BI-DB, die im PLM fehlen, per POST /vendors an (nur name + description, Kontakte im Text).

  .venv/bin/python plenty_vendors.py            # Trockenlauf
  .venv/bin/python plenty_vendors.py --apply    # anlegen + per GET verifizieren
Nur Lieferanten mit aktiven Produkten (Verkauf <= 365 Tage). Dublettencheck gegen die aktuelle PLM-Liste. Keine Bankdaten."""
import re
import sys

import plenty_products as pp
from plm_client import call

APPLY = "--apply" in sys.argv
CLEAN = {"(Old Lieferant E) Lieferant I Tetkstil": "Lieferant I"}  # Omar: Lieferant I ist der aktuelle Name, eigener Lieferant
n = lambda x: set(re.sub(r"(ltd|limited|co|inc|gmbh|pvt|sti|san|ve|ticaret|sanayi|dis|dıs|tekstil|textile|the|old|imp|exp|and|industry|trade|\W)+", " ", x.lower()).split())


def main():
    st, v = call("GET", "vendors", limit=100)
    have = [x["name"] for x in v]
    act = pp.psql("""select coalesce(k.supplier_name,''), count(distinct k.product_id) filter (where exists (select 1 from logistics.sku_sales_weekly w
      where w.ean=k.ean and w.instance_key=k.instance_key and w.week_start>=current_date-365)) from logistics.skus k where k.instance_key=1 group by 1""")
    info = {r[0]: r for r in pp.psql("select supplier_name, plenty_contact_name, plenty_email, plenty_phone from logistics.reorder_supplier_settings")}
    todo = []
    for name, akt in act:
        if not name or int(akt) == 0:
            continue
        if any(n(name) & n(x) and len(n(name) & n(x)) / len(n(name) | n(x)) >= 0.3 for x in have):
            continue
        clean = CLEAN.get(name, name)
        c = info.get(name) or info.get(clean)  # nur exakte Treffer, keine unscharfe Zuordnung
        parts = ["Quelle: Plenty-Lieferant", f"{akt} aktive Produkte"]
        if c and c[1]: parts.append(f"Kontakt: {c[1]}")
        if c and c[2]: parts.append(f"E-Mail: {c[2]}")
        if c and c[3]: parts.append(f"Tel: {c[3]}")
        todo.append((clean, " | ".join(parts)))
    print(f"fehlende Lieferanten: {len(todo)}")
    for nm, d in todo:
        print(f"  {nm} -> {d}")
    if not APPLY:
        return
    for nm, d in todo:
        if any(x.lower() == nm.lower() for x in [y["name"] for y in call("GET", "vendors", limit=100)[1]]):
            print(f"  {nm}: existiert inzwischen, uebersprungen")
            continue
        st, res = call("POST", "vendors", {"name": nm, "description": d})
        print(f"  {nm}: HTTP {st}")
    names = [y["name"] for y in call("GET", "vendors", limit=100)[1]]
    miss = [nm for nm, _ in todo if nm not in names]
    print("Verifikation:", "alle vorhanden" if not miss else f"FEHLEN {miss}", f"| Vendors gesamt {len(names)}")


if __name__ == "__main__":
    main()
