#!/usr/bin/env python3
"""Ergaenzt Vendors aus dem Tab SUPPLIERS der PRODUCTION_CONTROL_TOWER (Drive 01_LIVE_UEBERSICHTEN).

Uebernommen: Ansprechpartner (nur Vornamen laut Sheet), Land + Kategorie (an die Beschreibung angehaengt), MOQ je Farbe.
Nichts wird ueberschrieben oder erfunden; Platzhalter wie "Pruefen" werden ignoriert. Neu: Lieferant E.
  .venv/bin/python plm_vendors_enrich2.py            # Trockenlauf
  .venv/bin/python plm_vendors_enrich2.py --apply
"""
import os
import re
import sys

import openpyxl
import requests

from plm_client import call

APPLY = "--apply" in sys.argv
H = {"Authorization": f"Bearer {os.environ.get('LIFECYCLE_API_KEY', '')}", "Content-Type": "application/json"}
BASE = "https://app-be.lifecycleplm.com/api/v1/vendors"
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())
ALIAS = {  # Name im Sheet -> Name im PLM
    "Lieferant A": "Lieferant A", "Lieferant J": "Lieferant J", "Lieferant AA": "LIEFERANT_AA", "Lieferant C": "Lieferant C",
    "China Lieferant X": "LIEFERANT_X INDUSTRY CO.,LTD", "C-MAX / Fishjumping": "Ningbo Lieferant D Co., Ltd",
    "Lieferant AD": "Lieferant AD", "Lieferant V": "LIEFERANT_V LIMITED", "Lieferant AH": "LIEFERANT_AH",
    "Lieferant Y": "LIEFERANT_Y LIMITED", "Lieferant B": "Lieferant B Enterprises (Pvt) Ltd", "Lieferant E": None}
SKIP = re.compile(r"^(pr[uü]fen|zu pr[uü]fen|n/?a)?$", re.I)


def sheet_rows():
    ws = openpyxl.load_workbook("scans/PRODUCTION_CONTROL_TOWER.xlsx", data_only=True)["SUPPLIERS"]
    hdr = next(r for r in ws.iter_rows(values_only=True) if r and r[0] == "Supplier ID")
    col = {h: i for i, h in enumerate(hdr)}
    for r in ws.iter_rows(values_only=True):
        if r and str(r[0] or "").startswith("SUP-"):
            yield {k: r[i] for k, i in col.items()}


def main():
    vs = call("GET", "vendors")[1]
    plan = []
    for s in sheet_rows():
        name = s["Supplier Name"]
        plm = ALIAS.get(name)
        v = next((x for x in vs if x["name"] == plm), None) if plm else next((x for x in vs if norm(x["name"]) == norm(name)), None)
        contacts = [c.strip() for c in re.split(r"[/,]", str(s["Main Contact"] or "")) if c.strip() and not SKIP.match(c.strip())]
        bits = [f"Country: {s['Country']}" if s["Country"] else None,
                f"Capability: {s['Category / Capability']}" if s["Category / Capability"] else None]
        snippet = " | ".join(b for b in bits if b)
        moq = None
        m = re.search(r"(\d+)\s*/\s*color", str(s["MOQ"] or ""), re.I)
        if m:
            moq = int(m.group(1))
        acts = []
        if v is None:
            acts.append("NEU anlegen")
        desc = (v or {}).get("description") or ""
        if snippet and "Country:" not in desc:
            acts.append("Land/Kategorie")
        have = [norm(c.get("name")) for c in (v or {}).get("contacts", [])]
        new_contacts = [c for c in contacts if not any(norm(c) in h for h in have)]
        if new_contacts:
            acts.append("Kontakte " + ", ".join(new_contacts))
        if moq and (v or {}).get("minimumColorQuantity") != moq:
            acts.append(f"MOQ/Farbe {moq}")
        print(f"- {name}: {', '.join(acts) or 'nichts zu tun'}")
        if acts:
            plan.append((name, v, snippet, new_contacts, moq))
    if not APPLY:
        print(f"\nTrockenlauf: {len(plan)} Vendors betroffen. Mit --apply ausfuehren.")
        return
    for name, v, snippet, new_contacts, moq in plan:
        if v is None:
            st, res = call("POST", "vendors", {"name": name, "description": snippet})
            print(f"  {name}: POST -> {st}")
            v = next((x for x in call("GET", "vendors")[1] if norm(x["name"]) == norm(name)), None)
            if not v:
                print("   nicht angelegt - Abbruch"); sys.exit(1)
        g = requests.get(f"{BASE}/{v['id']}", headers=H, timeout=30).json()
        body = {k: g[k] for k in g if k not in ("recentOrders", "components", "samples", "performance")}
        desc = g.get("description") or ""
        if snippet and "Country:" not in desc:
            body["description"] = f"{desc} | {snippet}" if desc else snippet
        contacts = list(g.get("contacts", []))
        for c in new_contacts:
            contacts.append({"name": c, "main": not any(x.get("main") for x in contacts)})
        body["contacts"] = contacts
        if moq:
            body["minimumColorQuantity"] = moq
        body["expectedUpdatedAt"] = g["updatedAt"]
        r = requests.put(f"{BASE}/{v['id']}", json=body, headers=H, timeout=30)
        after = next(x for x in call("GET", "vendors")[1] if x["id"] == v["id"])
        ok = len(after["contacts"]) == len(contacts) and (not snippet or "Country:" in after["description"] or "Country:" in desc) and (not moq or after.get("minimumColorQuantity") == moq)
        print(f"  {name}: PUT -> {r.status_code} | Kontakte {len(after['contacts'])} | MOQ/Farbe {after.get('minimumColorQuantity')} | {'verifiziert' if ok else 'ABWEICHUNG ' + r.text[:200]}")
        if not ok:
            sys.exit(1)
    print("\nFertig, alle Vendors per GET verifiziert.")


if __name__ == "__main__":
    main()
