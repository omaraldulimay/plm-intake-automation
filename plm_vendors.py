#!/usr/bin/env python3
"""Vendor-Abgleich + Anlage/Ergaenzung im PLM.

Quelle: output/vendor_candidates.json (Lieferantenbloecke aus den PO-Excel-Dateien im Drive).
  .venv/bin/python plm_vendors.py                 # Trockenlauf: Abgleich + Plan (nur GET)
  .venv/bin/python plm_vendors.py --apply         # fehlende Vendors anlegen, bestehende ergaenzen

Regeln: nichts erfinden (Kontaktname = E-Mail-Adresse, wenn kein Name bekannt ist), Dublettencheck vor jedem POST,
nach jedem Schreibzugriff GET-Pruefung. Erst Versuch mit strukturierten contacts/addresses, bei Fehler Rueckfall
auf name+description (dieses Format ist erprobt).
"""
import json
import re
import sys
from pathlib import Path

from plm_client import call

ROOT = Path(__file__).parent
APPLY = "--apply" in sys.argv
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def clean_name(n):
    n = re.sub(r"\s+", " ", n).strip().rstrip(".").strip()
    return {"Lieferant A LTD": "Lieferant A"}.get(n, n)


def candidates():
    seen = {}
    for r in json.load(open(ROOT / "output/vendor_candidates.json")):
        key = clean_name(r["name"])
        d = seen.setdefault(key, {"name": key, "address": None, "emails": [], "phone": None, "sources": set()})
        d["address"] = d["address"] or (re.sub(r"\s+", " ", r["address"]).replace(" ,", ",").strip() if r.get("address") else None)
        for e in re.split(r"[/;,\s]+", r.get("email") or ""):
            if "@" in e and e.lower() not in d["emails"]:
                d["emails"].append(e.lower())
        d["phone"] = d["phone"] or r.get("phone")
        d["sources"].add(r["file"])
    return list(seen.values())


def bodies(c):
    desc = " | ".join(x for x in [c["address"], ", ".join(c["emails"]) or None, c["phone"]] if x)
    simple = {"name": c["name"], "description": desc}
    contacts = [{"name": e, "email": e, "main": i == 0, **({"phone": c["phone"]} if i == 0 and c["phone"] else {})}
                for i, e in enumerate(c["emails"])]
    if not contacts and c["phone"]:
        contacts = [{"name": c["name"], "phone": c["phone"], "main": True}]
    addresses = [{"name": c["name"], "line1": c["address"], "main": True}] if c["address"] else []
    return {**simple, "contacts": contacts, "addresses": addresses}, simple


def find(vendors, name):
    n = norm(name)
    return next((v for v in vendors if norm(v["name"]) == n or (len(n) > 6 and (n in norm(v["name"]) or norm(v["name"]) in n))), None)


def main():
    st, vendors = call("GET", "vendors")
    plan = []
    for c in candidates():
        ex = find(vendors, c["name"])
        full, simple = bodies(c)
        plan.append((c, ex, full, simple))
    print(f"{len(vendors)} Vendors im PLM, {len(plan)} Lieferanten aus den POs:\n")
    for c, ex, full, simple in plan:
        if not ex:
            print(f"- {c['name']}: NEU anlegen | Adresse: {c['address']} | E-Mail: {c['emails'] or '-'} | Tel: {c['phone'] or '-'}")
        else:
            miss = [k for k in ("contacts", "addresses") if not ex.get(k)]
            print(f"- {c['name']}: existiert ('{ex['name']}'), unvollstaendig: {miss or 'nein'} -> {'ergaenzen' if miss else 'ok'}")
    if not APPLY:
        print("\nTrockenlauf - nichts geschrieben. Mit --apply ausfuehren.")
        return

    for c, ex, full, simple in plan:
        if ex:
            miss = {k: full[k] for k in ("contacts", "addresses") if not ex.get(k) and full[k]}
            if not miss:
                continue
            import os, requests
            H = {"Authorization": f"Bearer {os.environ['LIFECYCLE_API_KEY']}", "Content-Type": "application/json"}
            url = f"https://app-be.lifecycleplm.com/api/v1/vendors/{ex['id']}"
            g = requests.get(url, headers=H, timeout=30)  # frisch laden: PUT verlangt den aktuellen Versionsstand
            cur, etag = g.json(), g.headers.get("ETag")
            base = {k: cur[k] for k in cur if k not in ("recentOrders", "components", "samples", "performance")}
            body = {**base, **miss, "expectedUpdatedAt": cur["updatedAt"]}  # Versionsstand wie die App (expectedUpdatedAt)
            for label, hdr in [("PUT + expectedUpdatedAt", None)]:
                r = requests.put(url, json=body, headers=H, timeout=30)
                print(f"  {c['name']}: {label} -> {r.status_code} {r.text[:300]}")
                if r.status_code in (200, 204):
                    break
            st, v = call("GET", f"vendors/{ex['id']}")
            print(f"    Pruefung: contacts={len(v.get('contacts', []))}, addresses={len(v.get('addresses', []))}")
            continue
        for label, body in (("mit contacts/addresses", full), ("nur name+description", simple)):
            if find(call("GET", "vendors")[1], c["name"]):
                print(f"  {c['name']}: existiert inzwischen - kein weiterer Versuch")
                break
            st, res = call("POST", "vendors", body)
            print(f"  {c['name']}: POST {label} -> {st} {json.dumps(res, ensure_ascii=False)[:300]}")
            if st in (200, 201):
                break
        v = find(call("GET", "vendors")[1], c["name"])
        print(f"    Pruefung: {'angelegt' if v else 'NICHT angelegt'}" + (f", contacts={len(v['contacts'])}, addresses={len(v['addresses'])}" if v else ""))


if __name__ == "__main__":
    main()
