#!/usr/bin/env python3
"""Dima 2.0 (Artikelstamm, Tab 'Eintragen') -> Lifecycle PLM, Stufe 1: bestehende Alpha-Styles AL29001-AL29033.

Dima enthaelt je Style eine Kopfzeile (Produzent, Material, EK, Gewicht) und Variantenzeilen (Farbe x Groesse).
Was dieses Skript tut:
  * Abgleich Dima <-> PLM ueber Artikelnummer (AL29xxx, Gross/Kleinschreibung egal) -> output/review/dima_vs_plm.csv
  * Update bestehender PLM-Produkte per PUT + expectedUpdatedAt (wie plm_apply_corrections.py):
    aktuell nur mainManufacturer = Lieferant A (bei allen 7 vorhandenen Styles leer).
  * Fehlende Styles werden hier NICHT angelegt (siehe plm_dima_create.py) -> nur gelistet.
Schutz: PUT liefert 500, speichert aber -> Pruefung immer per Listen-GET; vorher/nachher-Diff darf nur die
gewollten Felder enthalten; erledigte Schritte werden uebersprungen.

  .venv/bin/python plm_dima_sync.py            # Trockenlauf + Report
  .venv/bin/python plm_dima_sync.py --apply    # PUT ausfuehren
"""
import csv
import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path

import openpyxl

from plm_client import call

ROOT = Path(__file__).parent
APPLY = "--apply" in sys.argv
DIMA = Path(os.environ.get("DIMA_XLSX", Path.home() / "Downloads/☗ Dima 2.0 Grunddaten Artikelanlage.xlsx"))
ALPHA_VENDOR = "Lieferant A"
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())


def dima_styles():
    allrows = list(openpyxl.load_workbook(DIMA, read_only=True, data_only=True)["Eintragen"].iter_rows(values_only=True))
    gw = allrows[1].index("Gewicht netto")  # Zeile 0 = Hinweise, Zeile 1 = Spaltenkoepfe
    rows = allrows[1:]
    sty = OrderedDict()
    for r in rows:
        a = r[3]
        if not a or a == "Artikelnummer":
            continue
        s = sty.setdefault(a.upper(), {"colors": [], "sizes": [], "head": None})
        if r[8]:
            s["head"] = r
        else:
            if r[6] and r[6] not in s["colors"]:
                s["colors"].append(r[6])
            if r[7] and r[7] not in s["sizes"]:
                s["sizes"].append(r[7])
    out = []
    for a, s in sty.items():
        h = s["head"]
        if not h:
            continue
        mats = [(h[i], h[i + 1]) for i in (9, 11, 13) if h[i]]
        out.append({"art": a, "dept": h[4], "type": h[5], "producer": h[8], "ek": h[19], "weight_g": h[gw],
                    "material": ", ".join(f"{int(p) if p else ''}% {m}" for m, p in zip([h[11] or h[9], h[13], h[15]], [h[10], h[12], h[14]]) if m),
                    "colors": s["colors"], "sizes": s["sizes"], "mats": mats})
    return out


def products():
    out, p = [], 1
    while True:
        st, d = call("GET", "products", limit=100, page=p)
        assert st == 200, f"GET products -> {st}"
        out += d["data"]
        if p >= d["pagination"]["pages"]:
            return {x["id"]: x for x in out}
        p += 1


def vendor_id(name):
    st, d = call("GET", "vendors", limit=100)  # Vendors kommen als blanke Liste (keine Pagination)
    assert st == 200, f"GET vendors -> {st}"
    for v in d:
        if norm(v["name"]) == norm(name):
            return v["id"]
    raise SystemExit(f"Vendor {name} nicht im PLM")


def main():
    dima = dima_styles()
    cur = products()
    by_key = {}
    for p in cur.values():
        by_key[norm(p["name"])] = p
        by_key.setdefault(norm(p["sku"]), p)
    alpha = vendor_id(ALPHA_VENDOR)
    report, todo = [], []
    for d in dima:
        p = by_key.get(norm(d["art"]))
        row = {"artikelnr": d["art"], "typ": f"{d['dept']} {d['type']}", "ek_dima": d["ek"], "gewicht_g": d["weight_g"],
               "material": d["material"], "farben_dima": len(d["colors"]), "groessen_dima": " ".join(d["sizes"]),
               "im_plm": bool(p), "plm_id": p["id"] if p else "", "plm_varianten": len(p["variants"]) if p else "",
               "plm_groessen": " ".join(p["sizes"]) if p else "", "plm_hersteller": (p.get("mainManufacturer") or {}).get("name", "") if p else "",
               "aktion": ""}
        if not p:
            row["aktion"] = "ANLEGEN (nur minimal moeglich: plm_dima_create.py)"
        elif (p.get("mainManufacturer") or {}).get("id") != alpha:
            row["aktion"] = "mainManufacturer -> Lieferant A"
            todo.append((p["id"], d["art"]))
        else:
            row["aktion"] = "ok"
        report.append(row)
    out = ROOT / "output/review/dima_vs_plm.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(report[0]))
        w.writeheader()
        w.writerows(report)
    print(f"Dima-Styles: {len(dima)} | im PLM: {sum(r['im_plm'] for r in report)} | fehlen: {sum(not r['im_plm'] for r in report)}")
    print(f"Update offen: {len(todo)} -> {[a for _, a in todo]}\nReport: {out}")
    if not APPLY or not todo:
        print("Trockenlauf." if not APPLY else "Nichts zu tun.")
        return
    # Feldformat von PUT ist nicht dokumentiert -> Kandidaten der Reihe nach, am ersten Style, Stopp beim ersten Treffer
    candidates = [{"mainManufacturer": alpha}, {"mainManufacturer": {"id": alpha}}, {"mainManufacturerId": alpha}, {"manufacturerId": alpha}]
    fmt = None
    for pid, art in todo:
        before = products()[pid]
        tries = [fmt] if fmt else candidates
        for ch in tries:
            st, res = call("PUT", f"products/{pid}", {**ch, "expectedUpdatedAt": before["updatedAt"]})
            after = products()[pid]
            ok = (after.get("mainManufacturer") or {}).get("id") == alpha
            diff = {k for k in set(before) | set(after) if k != "updatedAt" and before.get(k) != after.get(k)}
            print(f"  {art}: PUT {list(ch)} -> HTTP {st}, uebernommen={ok}, weitere Aenderungen={sorted(diff - {'mainManufacturer'})}")
            if diff - {"mainManufacturer"}:
                sys.exit("Unerwartete Aenderung -> Abbruch")
            if ok:
                fmt = ch
                before = after
                break
        else:
            sys.exit(f"{art}: kein Feldformat hat gegriffen -> Abbruch (Antwort: {json.dumps(res, ensure_ascii=False)[:300]})")
    print("Fertig, alle per Listen-GET verifiziert.")


if __name__ == "__main__":
    main()
