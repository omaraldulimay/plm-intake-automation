#!/usr/bin/env python3
"""Sonderformate: .ods (Lieferant AG) -> temporaere xlsx + Standard-Extraktor, Lieferant V (PI-basiert), Lieferant B (Farbe x Groesse-Tabelle).
  .venv/bin/python extract_po_misc.py
Ausgabe: output/po/*.json (wie die anderen Extraktoren). Nichts wird korrigiert, Auffaelligkeiten stehen unter "flags"."""
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import openpyxl

import extract_po_excel as std

ROOT = Path(__file__).parent
NS = {"t": "urn:oasis:names:tc:opendocument:xmlns:table:1.0", "x": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
      "o": "urn:oasis:names:tc:opendocument:xmlns:office:1.0"}
T = "{%s}" % NS["t"]
O = "{%s}" % NS["o"]


def ods_to_xlsx(src, dst):
    root = ET.fromstring(zipfile.ZipFile(src).read("content.xml"))
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for tab in root.iter(T + "table"):
        ws = wb.create_sheet(tab.get(T + "name")[:31])
        r = 0
        for row in tab.iter(T + "table-row"):
            rep_r = int(row.get(T + "number-rows-repeated", "1"))
            vals, c = [], 0
            for cell in row:
                if cell.tag not in (T + "table-cell", T + "covered-table-cell"):
                    continue
                rep_c = int(cell.get(T + "number-columns-repeated", "1"))
                vt = cell.get(O + "value-type")
                if vt in ("float", "percentage", "currency"):
                    v = float(cell.get(O + "value"))
                elif vt in ("string", "date"):
                    v = cell.get(O + "date-value") or "\n".join("".join(p.itertext()) for p in cell.findall("x:p", NS))
                else:
                    v = None
                if v is not None and rep_c < 50:
                    for k in range(rep_c):
                        vals.append((c + k + 1, v))
                c += rep_c
            if vals and rep_r < 50:
                for k in range(rep_r):
                    for col, v in vals:
                        ws.cell(r + k + 1, col, v)
            r += rep_r
    wb.save(dst)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def lieferant_v(f):
    ws = openpyxl.load_workbook(f, data_only=True)["Purchase Order"]
    kv = {}
    for row in ws.iter_rows(min_row=3, max_row=9):
        for c in row:
            if isinstance(c.value, str) and c.value.strip() in ("PO #", "PO Date", "PI No.", "PI Date", "Shipment Date / ETD", "ETA Hamburg", "Country of Origin", "Incoterms", "Payment Term", "Balance"):
                kv[c.value.strip()] = ws.cell(c.row, c.column + 1).value
    hdr = next(c.row for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("PRODUCT NAME"))
    items, flags = [], []
    for r in range(hdr + 1, ws.max_row + 1):
        style = ws.cell(r, 1).value
        qty, price = num(ws.cell(r, 9).value), num(ws.cell(r, 8).value)
        if not style or qty is None:
            if style and str(style).upper().startswith("TOTAL"):
                break
            continue
        items.append({"style_no": str(style).strip(), "description": ws.cell(r, 2).value, "unit_price": price, "total_qty_stated": qty,
                      "line_total_stated": num(ws.cell(r, 11).value), "variants": [], "sizes": {}, "checks": []})
        if price and num(ws.cell(r, 11).value) is not None and abs(price * qty - num(ws.cell(r, 11).value)) > 1:
            flags.append(f"{style}: Preis*Menge != TOTAL")
    flags.append("Farben und Groessenaufteilung fehlen in der Datei (TBA)")
    pcs, val = sum(i["total_qty_stated"] for i in items), sum(i["unit_price"] * i["total_qty_stated"] for i in items)
    return {"layout": "lieferant_v", "purchase_order": {"po_number": kv.get("PO #"), "date": str(kv.get("PO Date"))[:10], "shipment_date": str(kv.get("Shipment Date / ETD")), "eta_hamburg": kv.get("ETA Hamburg"),
                                                      "incoterms": kv.get("Incoterms"), "country_of_origin": kv.get("Country of Origin")},
            "supplier": {"name": "LIEFERANT_V LIMITED"}, "items": items, "totals": {"sum_positions": val},
            "terms": {"payment_terms_text": f"{kv.get('Payment Term')} / {kv.get('Balance')}"}, "flags": flags, "stats": {"items": len(items), "pieces": pcs}}


def lieferant_b(f):
    ws = openpyxl.load_workbook(f, data_only=True)["Official PO"]
    hdr = next(c.row for row in ws.iter_rows() for c in row if c.value == "Category")
    sizes = {c.column: str(c.value) for c in ws[hdr] if str(c.value) in ("XS", "S", "M", "L", "XL", "XXL", "3XL")}
    tot_col = next(c.column for c in ws[hdr] if c.value == "TOTAL")
    items, flags = {}, []
    for r in range(hdr + 1, ws.max_row + 1):
        cat, style, color = ws.cell(r, 1).value, ws.cell(r, 2).value, ws.cell(r, 4).value
        if not style or not color:
            continue
        q = {sz: num(ws.cell(r, c).value) or 0 for c, sz in sizes.items()}
        tot = num(ws.cell(r, tot_col).value)
        it = items.setdefault((cat, style), {"style_no": f"{cat} {style}", "description": ws.cell(r, 3).value, "unit_price": None, "variants": [], "checks": []})
        it["variants"].append({"colour": str(color), "sizes": q, "total_stated": tot})
        if tot is not None and abs(sum(q.values()) - tot) > 0.5:
            flags.append(f"{style} {color}: Summe {sum(q.values()):g} != TOTAL {tot:g}")
    flags.append("Keine Preise in der Datei")
    lst = list(items.values())
    for it in lst:
        it["total_qty_computed"] = sum(sum(v["sizes"].values()) for v in it["variants"])
    return {"layout": "lieferant_b", "purchase_order": {"po_number": None, "date": None}, "supplier": {"name": "Lieferant B Enterprises (Pvt) Ltd"}, "items": lst,
            "totals": {}, "terms": {}, "flags": flags, "stats": {"items": len(lst), "pieces": sum(i["total_qty_computed"] for i in lst)}}


def main():
    out = ROOT / "output" / "po"
    out.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "output" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    # Lieferant AG .ods -> xlsx -> Standard-Extraktor
    y = tmp / "PO_LIEFERANT_AG_18.03.2026.xlsx"
    ods_to_xlsx(ROOT / "scans/PO_LIEFERANT_AG_18.03.2026.xlsx.ods", y)
    std.main([str(y)])
    for name, fn, path in [("PO_Lieferant V_KCCN0513", lieferant_v, ROOT / "scans/vendors/pages/Smilodox_PO_Lieferant V_KCCN0513.xlsx"),
                           ("LIEFERANT_B_Official_PO", lieferant_b, ROOT / "scans/vendors/pages/LIEFERANT_B_Official_PO_Size_Breakdown.xlsx")]:
        d = fn(path)
        d["source_file"], d["source_sheet"] = path.name, "main"
        (out / f"{name}__main.json").write_text(json.dumps(d, indent=2, ensure_ascii=False))
        print(f"+ {path.name}: {d['stats']['items']} Styles, {d['stats']['pieces']:g} Stk, {len(d['flags'])} Hinweise -> {d['flags'][:3]}")


if __name__ == "__main__":
    main()
