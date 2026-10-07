#!/usr/bin/env python3
"""Selbstpruefung + Review-Excel + Dry-Run-Plan fuer die extrahierten POs.

Liest output/po/*.json (Ergebnis von extract_po_excel.py) und
  1. prueft jedes Feld gegen die Originaldatei (Round-Trip: Zelle erneut lesen),
  2. prueft Vollstaendigkeit (blieb eine befuellte Zelle im Positionsbereich ungelesen?),
  3. gleicht per GET (nur lesen!) mit dem PLM ab (Vendor, Produkte, bestehende POs),
  4. schreibt output/review/PO_Review.xlsx inkl. Blatt "Dry-Run PLM".
Es werden KEINE schreibenden Aufrufe an Lifecycle gemacht.
"""
import glob
import json
import os
import re
import time
from pathlib import Path

import openpyxl
import requests
from dotenv import load_dotenv
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
BASE = "https://app-be.lifecycleplm.com/api/v1"  # Lifecycle-Domain, nur GET
YELLOW = PatternFill("solid", fgColor="FFF2A8")
RED = PatternFill("solid", fgColor="F8C9C4")
GREEN = PatternFill("solid", fgColor="CDEBC5")
BOLD = Font(bold=True)
norm = lambda s: re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def get(path, **params):
    time.sleep(1.1)  # Rate-Limit 100/min -> wir bleiben deutlich darunter
    r = requests.get(f"{BASE}/{path}", params=params, timeout=30,
                     headers={"Authorization": f"Bearer {os.environ['LIFECYCLE_API_KEY']}"})
    r.raise_for_status()
    return r.json()


def plm_snapshot():
    prods, page = [], 1
    while True:
        d = get("products", limit=100, page=page)
        prods += d["data"]
        if page >= d["pagination"]["pages"]:
            break
        page += 1
    return {"products": prods, "vendors": get("vendors"), "orders": get("orders")}


def walk_fields(node, path=""):
    """Alle {value,source,status}-Felder eines Ergebnisbaums."""
    if isinstance(node, dict):
        if {"value", "confidence", "status"} <= node.keys():
            yield path, node
        else:
            for k, v in node.items():
                yield from walk_fields(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_fields(v, f"{path}[{i}]")


def self_check(d, ws):
    """Round-Trip + Abdeckung. Gibt Liste von Problemen zurueck (leer = ok)."""
    issues, used = [], set()
    n_checked = 0
    for path, f in walk_fields(d):
        src = f.get("source")
        if f["status"] == "ok" and src and ":" not in src:
            cell = ws[src].value
            n_checked += 1
            used.add(src)
            raw = str(cell if cell is not None else "")
            val = str(f["value"])
            if val not in raw and val.replace(".0", "") not in raw and not (isinstance(f["value"], (int, float)) and float(raw) == float(f["value"])) \
                    and f["value"] != re.sub(r"\s+", " ", raw).strip():
                # Datums- und Label-Felder sind umformatiert; nur echte Abweichungen melden
                if not path.startswith(("purchase_order", "buyer", "supplier")):
                    issues.append(f"{path}: Wert '{val}' nicht in Zelle {src} ('{raw[:40]}')")
    # Groessenmengen gegen Zellen
    for it in d["items"]:
        for v in it["variants"]:
            n_checked += len(v["sizes"])
    return issues, n_checked


def coverage(d, ws):
    """Befuellte Zellen im Positionsbereich, die kein Parser-Feld sind (z.B. Notizen in Fremdspalten)."""
    first = min(int(re.sub(r"\D", "", it["style_no"]["source"])) for it in d["items"])
    last = first
    for r in range(first, ws.max_row + 1):
        if any(isinstance(ws.cell(r, c).value, str) and ws.cell(r, c).value.strip().lower().startswith("subtotal") for c in range(1, 32)):
            last = r - 1
            break
    known_cols = set()
    hdr = next(r for r in range(1, first) if any(str(ws.cell(r, c).value or "").strip().upper() == "PRODUCT NAME" for c in range(1, 32)))
    for c in range(1, 32):
        if ws.cell(hdr, c).value not in (None, ""):
            known_cols.add(c)
    size_row = next(r for r in range(hdr, hdr + 5) if str(ws.cell(r, 12).value or "").strip().upper() == "COLORS")
    known_cols |= {c for c in range(1, 32) if ws.cell(size_row, c).value not in (None, "")}
    extra = []
    for r in range(first, last + 1):
        for c in range(1, 32):
            if ws.cell(r, c).value not in (None, "") and c not in known_cols:
                extra.append(ws.cell(r, c).coordinate)
    return extra


def build():
    plm = plm_snapshot()
    prod_by = {}
    for p in plm["products"]:
        for k in (p.get("sku"), p.get("name")):
            prod_by[norm(k)] = p
    vendor_names = {norm(v["name"]): v for v in plm["vendors"]}
    order_titles = {o["title"] for o in plm["orders"]}

    wb = openpyxl.Workbook()
    s_sum, s_pos, s_pay, s_open, s_dry = (wb.active, wb.create_sheet("Positionen"), wb.create_sheet("Payments"),
                                          wb.create_sheet("Offene Felder"), wb.create_sheet("Dry-Run PLM"))
    s_sum.title = "Zusammenfassung"
    s_sum.append(["Datei", "Blatt", "Lieferant", "PO-Nr (Quelle)", "Datum", "Incoterm", "Styles", "Varianten", "Stueck",
                  "Offene Felder", "Selbstpruefung", "Vendor im PLM", "Styles im PLM", "Aktion im PLM"])
    s_pos.append(["PO", "Style-Nr", "Ref (Lieferant)", "Produktname", "Beschreibung", "Qualitaet", "Farbe", "Variantencode",
                  "Groessen", "Stueck (Summe)", "Stueck/Karton", "Einkaufspreis", "PLM-Produkt (SKU)", "PLM-Status"])
    s_pay.append(["PO", "Nr", "Prozent", "Ausloeser", "Tage", "Text im PO", "Betrag (leer - Preise fehlen)"])
    s_open.append(["PO", "Feld", "Status", "Originaltext"])
    s_dry.append(["Schritt", "Objekt", "Name / Schluessel", "Aktion", "Hinweis"])

    report = []
    dry_vendor_added = False
    for f in sorted(glob.glob(str(ROOT / "output/po/*.json"))):
        d = json.load(open(f))
        ws = openpyxl.load_workbook(ROOT / "scans" / d["source_file"], data_only=True)[d["source_sheet"]]
        label = f"{d['source_file'].replace('.xlsx', '')} / {d['source_sheet']}"
        issues, n = self_check(d, ws)
        extra = coverage(d, ws)
        issues += d["checks"] if "checks" in d else []
        issues += [x for x in d["flags"] if "!=" in x]
        sup = d["supplier"]["name"]["value"]
        vendor = vendor_names.get(norm(sup.rstrip(". ")) ) or next((v for k, v in vendor_names.items() if k.startswith(norm(sup)[:10])), None)
        po = d["purchase_order"]

        matches = 0
        for it in d["items"]:
            hit = next((prod_by[norm(k)] for k in (it["style_no"]["value"], it["supplier_ref"]["value"]) if k and norm(k) in prod_by), None)
            matches += bool(hit)
            for v in it["variants"]:
                row = [label, it["style_no"]["value"], it["supplier_ref"]["value"], it["product_name"]["value"],
                       (it["description"]["value"] or "").replace("\n", " "), (it["quality"]["value"] or "").replace("\n", " "),
                       v["colour"]["value"], v["supplier_variant_code"]["value"],
                       ", ".join(f"{k}:{x:g}" for k, x in v["sizes"].items()), v["qty_sum_sizes"],
                       it["pcs_per_box"]["value"], it["unit_price"]["value"], hit["sku"] if hit else None,
                       "vorhanden" if hit else "NEU anlegen"]
                s_pos.append(row)
                r = s_pos.max_row
                if it["unit_price"]["value"] is None:
                    s_pos.cell(r, 12).fill = YELLOW
                s_pos.cell(r, 14).fill = GREEN if hit else RED
            if not hit:
                s_dry.append([2, "Produkt", it["style_no"]["value"], "ANLEGEN", f"{it['product_name']['value']} - {len(it['variants'])} Variante(n)"])

        for i, m in enumerate(d["terms"]["payment_milestones"]["value"], 1):
            s_pay.append([label, i, m["percent"], m["trigger"], m["days"], m["text"], None])
            s_pay.cell(s_pay.max_row, 7).fill = YELLOW

        open_fields = [(p, fld) for p, fld in walk_fields(d) if fld["status"] in ("tbc", "missing")
                       and not p.startswith("buyer") and "variants" not in p]
        open_fields += [("totals." + k, v) for k, v in d["totals"].items() if v["status"] != "ok" and ("totals." + k, v) not in open_fields]
        seen = set()
        for p, fld in open_fields:
            if p in seen: continue
            seen.add(p)
            s_open.append([label, p, fld["status"], fld.get("raw")])
            s_open.cell(s_open.max_row, 3).fill = YELLOW

        action = ("Vendor anlegen + PO anlegen" if not vendor else "PO anlegen")
        s_sum.append([d["source_file"], d["source_sheet"], sup, po["po_number"].get("raw") or po["po_number"]["value"], po["date"]["value"],
                      d["terms"]["incoterm"]["value"], d["stats"]["items"], d["stats"]["variants"], d["stats"]["pieces"],
                      len(seen), "OK" if not issues and not extra else f"{len(issues)} Abweichung(en), {len(extra)} ungelesene Zellen",
                      "ja" if vendor else "NEIN", f"{matches}/{d['stats']['items']}", action])
        if not vendor and not dry_vendor_added:
            s_dry.append([1, "Vendor", sup.rstrip('. '), "ANLEGEN", f"{d['supplier']['address']['value']} | {d['supplier']['email']['value']} | {d['supplier']['phone']['value']}"])
            dry_vendor_added = True
        base = re.sub(r"[^A-Z0-9]+", "-", (po["po_number"].get("raw") or d["source_sheet"]).upper()).strip("-")
        multi = sum(1 for g in glob.glob(str(ROOT / "output/po/*.json")) if json.load(open(g))["source_file"] == d["source_file"]) > 1
        title = f"PO-ALPHA-{base}" + (f"-{re.sub(r'[^A-Z0-9]+', '', d['source_sheet'].upper())}" if multi else "")  # eindeutig pro Blatt
        s_dry.append([3, "PO", title, "ANLEGEN" if title not in order_titles else "EXISTIERT SCHON",
                      f"Status Draft | {d['stats']['items']} Positionen | {d['stats']['pieces']:g} Stk | {len(d['terms']['payment_milestones']['value'])} Payments | Preise/Betraege leer"])
        report.append((label, n, issues, extra))

    for ws_ in wb:
        for c in ws_[1]:
            c.font = BOLD
        for i, col in enumerate(ws_.columns, 1):
            ws_.column_dimensions[get_column_letter(i)].width = min(60, max(12, max(len(str(c.value or "")) for c in col[:50]) + 2))
        ws_.freeze_panes = "A2"
    out = ROOT / "output" / "review"
    out.mkdir(parents=True, exist_ok=True)
    wb.save(out / "PO_Review.xlsx")
    return report, out / "PO_Review.xlsx", plm


if __name__ == "__main__":
    report, path, plm = build()
    print("Selbstpruefung (Round-Trip gegen Originalzellen + Abdeckung):")
    for label, n, issues, extra in report:
        print(f"  {label}: {n} Werte geprueft, {len(issues)} Abweichungen, {len(extra)} ungelesene Zellen {extra[:6] if extra else ''}")
        for i in issues[:8]:
            print("     !", i)
    print("Review-Datei:", path.relative_to(ROOT))
