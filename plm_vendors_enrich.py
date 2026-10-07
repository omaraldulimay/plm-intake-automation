#!/usr/bin/env python3
"""Ergaenzt Vendors im PLM aus der Drive-Datei PAYMENT/"PAYING DETAILS SPREADSHEET.xlsx".

Uebernommen werden: Ansprechpartner (Vorname laut "X VON Firma"), Zahlungsbedingungen, rechtlicher Zahlungsempfaenger,
Adressen. NICHT uebernommen: Kontonummern, SWIFT, Bankname (Freitextfelder sind fuer alle PLM-Nutzer/Lieferantenportal sichtbar).
Nichts wird ueberschrieben: Beschreibung wird nur angehaengt, Kontakte/Adressen nur ergaenzt.
Quelle sind die Zeilen der Datei (hier als Daten erfasst, ohne Bankdaten).

  .venv/bin/python plm_vendors_enrich.py            # Trockenlauf (nur GET)
  .venv/bin/python plm_vendors_enrich.py --apply
Wie die Aenderung geschrieben wird: PUT /vendors/{id} mit vollem Stand + expectedUpdatedAt (Mechanismus der App).
"""
import json
import os
import re
import sys

import requests

from plm_client import call

APPLY = "--apply" in sys.argv
H = {"Authorization": f"Bearer {os.environ.get('LIFECYCLE_API_KEY', '')}", "Content-Type": "application/json"}
BASE = "https://app-be.lifecycleplm.com/api/v1/vendors"
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())

# plm: Name im PLM (None = neu anlegen), contact: Vorname laut Datei, terms: Zahlungsbedingungen laut Datei,
# payee: rechtlicher Zahlungsempfaenger, address: Adresse des Zahlungsempfaengers (falls in der Datei)
ROWS = [
    {"plm": "Lieferant H garment company", "contact": "Dominik", "goods": "Rain jacket",
     "terms": "20% Deposit 40% Before shipment 40% Before arrival", "payee": "FUJIAN LIEFERANT_H GARMENTS CO.,LTD"},
    {"plm": "LIEFERANT_V LIMITED", "contact": "Eric", "goods": "Outerwear",
     "terms": "20% Deposit 80% against Copy of B/L", "payee": "LIEFERANT_V LIMITED"},
    {"plm": "LIEFERANT_AA", "contact": "Faye", "goods": "Jackets / puffer jacket",
     "terms": "20% deposit before production 15% by shipment 35% 40 days after shipment 30% 80 days after shipping",
     "payee": "LIEFERANT_Z COMPANY LIMITED",
     "address": "SHOP 40, 2/F., HOUSTON CENTER, 63 MODY ROAD, TSIM SHA TSUI, HONG KONG"},
    {"plm": "LIEFERANT_X INDUSTRY CO.,LTD", "contact": "Doreen", "goods": "Outerwear",
     "terms": "25% Deposit 75% against Copy of B/L", "payee": "LIEFERANT_X INDUSTRY CO., LTD"},
    {"plm": "LIEFERANT_Y LIMITED", "contact": "Lily", "goods": "Shoes",
     "terms": "TT 15% deposit 40% before the shipment and the balance 45% after the shipment within one month before release the B/L",
     "payee": "LIEFERANT_Y LIMITED",
     "address": "NO.701, JINGFA BLDG, XIEDOU ROAD, CHENDAI TOWN, JINJIANG CITY, FUJIAN, CHINA"},
    {"plm": "Lieferant C", "contact": "Nicole Chen", "goods": "Sportswear and outerwear",
     "terms": "30% Deposit 70% against Copy of B/L", "payee": "Lieferant C Co., Ltd.",
     "address": "Area A-1, 10/F, NO.93-95, Anling 2nd Road, Huli District, Xiamen, China"},
    {"plm": "LIEFERANT_W CO., LTD", "contact": "Debbie", "goods": None, "terms": None, "payee": None},
    {"plm": "LIEFERANT_AH", "contact": "Elin", "goods": None, "terms": None, "payee": None},
    {"plm": "Lieferant P Co.,Ltd.", "contact": None, "goods": "Bottles (Lieferant T)",
     "terms": "15% deposit before production 20% after inspection 15% before shipment 65% 30 days after shipment",
     "payee": "LIEFERANT_P CO., LTD.",
     "address": "ROOM 612, BUILDING 1, JIANGNANXINGZUO, NO.529 CHUNXIAO ROAD, BINJIANG DISTRICT, HANGZHOU CITY, ZHEJIANG, P. R. CHINA",
     "note": "Quelle nennt 15+20+15+65 = 115 %, bitte Zahlungsplan pruefen"},
    {"plm": "Lieferant U", "contact": None, "goods": "Caps",
     "terms": "30% deposit before production 70% balance against B/L copy", "payee": "Lieferant S & Accessories Limited"},
    {"plm": "Lieferant A", "contact": None, "goods": "Reorder FITX",
     "terms": "15% deposit before production 10% by shipment 35% 40 days after shipment 40% 80 days after shipping", "payee": None},
    {"plm": None, "new_name": "Xiamen Lieferant G Industry Co., Ltd", "contact": None, "goods": "Bags",
     "terms": "20% deposit before production 80% balance against B/L copy", "payee": "XIAMEN LIEFERANT_G INDUSTRY CO., LTD",
     "address": "Hongxiang BLDG. 3/F, No.258 Hubin S Road, Xiamen 361001, China"},
    {"plm": None, "new_name": "Lieferant AI", "contact": None, "goods": "Gloves",
     "terms": "15% deposit before production 10% by shipment 35% 40 days after shipment 40% 80 days after shipping", "payee": None},
    {"plm": None, "new_name": "Ningbo Lieferant D Co., Ltd", "contact": "Anna Jin", "contact_phone": "0574-87400330-803",
     "goods": "Leggings, fleece jackets (PI LIEFERANT_D-ALI20260821: 133,900 pcs, USD 347,755.50, FOB, ETD 15.10.2026)",
     "terms": "20% deposit, 30% balance against B/L; 30% balance 35 days after shipment, 20% balance 60 days after shipment",
     "payee": "Ningbo Lieferant D Co., Ltd",
     "address": "Room 604, No.76, Building 10, Binyue Center, Jiangbei District, Ningbo, Zhejiang, China"},
    {"plm": None, "new_name": "Lieferant AL", "contact": None, "goods": "Underwear (reorder)",
     "terms": "30% deposit in advance 70% balance payable within 100 days after shipment", "payee": None},
]


def snippet(r):
    parts = []
    if r.get("terms"):
        parts.append(f"Payment terms: {r['terms']}")
    if r.get("payee"):
        parts.append(f"Payee: {r['payee']}")
    if r.get("goods"):
        parts.append(f"Goods: {r['goods']}")
    return " | ".join(parts)


def vendors():
    return call("GET", "vendors")[1]


def main():
    vs = vendors()
    todo = []
    for r in ROWS:
        v = next((x for x in vs if x["name"] == r["plm"]), None) if r["plm"] else next((x for x in vs if norm(x["name"]) == norm(r["new_name"])), None)
        name = r["plm"] or r["new_name"]
        actions = []
        if v is None:
            actions.append("NEU anlegen")
        desc = (v or {}).get("description") or ""
        s = snippet(r)
        if s and "Payment terms:" not in desc:
            actions.append("Zahlungsbedingungen in Beschreibung")
        if r.get("contact") and not any(norm(r["contact"].split()[0]) in norm(c.get("name")) for c in (v or {}).get("contacts", [])):
            actions.append(f"Kontakt {r['contact']}")
        if r.get("address") and not any(norm(r["address"])[:25] in norm(a.get("line1")) for a in (v or {}).get("addresses", [])):
            actions.append("Adresse")
        print(f"- {name}: {', '.join(actions) or 'nichts zu tun'}" + (f"  [Hinweis: {r['note']}]" if r.get("note") else ""))
        if actions:
            todo.append((r, v, name))
    if not APPLY:
        print(f"\nTrockenlauf: {len(todo)} Vendors betroffen. Mit --apply ausfuehren.")
        return

    for r, v, name in todo:
        if v is None:
            st, res = call("POST", "vendors", {"name": name, "description": snippet(r)})
            print(f"  {name}: POST -> {st}")
            v = next((x for x in vendors() if norm(x["name"]) == norm(name)), None)
            if not v:
                print("   nicht angelegt - Abbruch")
                sys.exit(1)
        g = requests.get(f"{BASE}/{v['id']}", headers=H, timeout=30).json()
        base = {k: g[k] for k in g if k not in ("recentOrders", "components", "samples", "performance")}
        desc = g.get("description") or ""
        s = snippet(r)
        if s and "Payment terms:" not in desc:
            base["description"] = f"{desc} | {s}" if desc else s
        contacts = list(g.get("contacts", []))
        if r.get("contact") and not any(norm(r["contact"].split()[0]) in norm(c.get("name")) for c in contacts):
            contacts.append({"name": r["contact"], "main": not any(c.get("main") for c in contacts),
                             **({"phone": r["contact_phone"]} if r.get("contact_phone") else {})})
        addresses = list(g.get("addresses", []))
        if r.get("address") and not any(norm(r["address"])[:25] in norm(a.get("line1")) for a in addresses):
            addresses.append({"name": r.get("payee") or name, "line1": r["address"], "main": not any(a.get("main") for a in addresses)})
        base["contacts"], base["addresses"] = contacts, addresses
        base["expectedUpdatedAt"] = g["updatedAt"]
        resp = requests.put(f"{BASE}/{v['id']}", json=base, headers=H, timeout=30)
        after = next(x for x in vendors() if x["id"] == v["id"])
        ok = len(after["contacts"]) == len(contacts) and len(after["addresses"]) == len(addresses) and (not s or "Payment terms:" in after["description"] or "Payment terms:" in desc)
        print(f"  {name}: PUT -> {resp.status_code} | Kontakte {len(after['contacts'])}, Adressen {len(after['addresses'])} | {'verifiziert' if ok else 'ABWEICHUNG: ' + resp.text[:200]}")
        if not ok:
            sys.exit(1)
    print("\nFertig, alle Vendors per GET verifiziert.")


if __name__ == "__main__":
    main()
