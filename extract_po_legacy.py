#!/usr/bin/env python3
"""Liest PO-Excel-Dateien im aelteren Layout (eine Zeile je Style, Groessenmengen als Text in 'Size wise Qty').

Aufruf:  .venv/bin/python extract_po_legacy.py datei1.xlsx [datei2.xlsx ...]
Ausgabe: output/po/<datei>__<blatt>.json (gleiches Grundschema wie extract_po_excel.py, Feld "layout": "legacy")
Es wird NICHTS korrigiert: Widersprueche (Summe der Groessen != Total QTY, doppelte Bloecke mit anderen Zahlen,
Summe Preis*Menge != TOTAL) landen unter "checks"/"flags"."""
import json
import re
import sys
from pathlib import Path

import openpyxl

SIZE_PAIR = re.compile(r"(?P<size>\d{2}\s*/\s*\d{2}|\d?X{0,2}[SL]|XXS|XS|S|M|L|XL|\d?XL|XXL|[2-6]XL|ONE\s*SIZE|\d{2,3})\s*[-:]\s*(?P<qty>[\d.,]+)", re.I)


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def s_(v):
    return None if v is None or str(v).strip() == "" else str(v).strip()


def s(v):
    return None if v is None or str(v).strip() == "" else str(v).strip()


def parse_sizes(text, checks, label):
    """'XL - 350\\n5XL - 15 (JUST FOR FITX)' -> {'XL': 350, '5XL': 15}; doppelte Bloecke werden zusammengefasst."""
    out = {}
    for m in SIZE_PAIR.finditer(str(text or "")):
        size = re.sub(r"\s+", "", m.group("size")).upper()
        qty = num(m.group("qty"))
        if qty is None:
            continue
        if size in out:
            if out[size] != qty:
                checks.append(f"{label}: Groesse {size} doppelt mit verschiedenen Mengen ({out[size]:g} / {qty:g})")
            continue  # gleiche Zahl nochmal = doppelt eingefuegter Block
        out[size] = qty
    return out


def lab(ws, label, r0=1, r1=18):
    for r in range(r0, r1 + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if isinstance(v, str) and v.strip().lower().startswith(label.lower()):
                rest = v.split(":", 1)[1].strip() if ":" in v else ""
                if rest:
                    return rest
                for cc in range(c + 1, min(c + 8, ws.max_column + 1)):
                    if s(ws.cell(r, cc).value):
                        return s(ws.cell(r, cc).value)
    return None


def parse_sheet(ws):
    hdr = next((c.row for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.strip().upper() == "PRODUCT NAME"), None)
    if not hdr:
        return None
    col = {}
    for c in ws[hdr]:
        if isinstance(c.value, str):
            k = " ".join(c.value.upper().split())
            col.update({"PRODUCT NAME": {"product": c.column}, "DESCRIPTION": {"desc": c.column}, "QUALITY": {"quality": c.column},
                        "SIZE WISE QTY": {"sizes": c.column}, "PCS PER BOX": {"box": c.column}, "BOX SIZE": {"box": c.column},
                        "PRICE USD": {"price": c.column}, "PRICE": {"price": c.column}, "TOTAL QTY": {"qty": c.column}, "QTY": {"qty": c.column},
                        "SIZE": {"sizecol": c.column}, "COLOUR": {"colour": c.column}, "TOTAL": {"total": c.column}}.get(k, {}))
    if "product" not in col or "sizes" not in col:
        return None
    end = ws.max_row
    for r in range(hdr + 1, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if isinstance(v, str) and (v.strip().lower().startswith("subtotal") or v.strip().upper() == "NOTE" or v.strip().upper().startswith("NOTE:")):
                end = min(end, r)
    foc_row = next((r for r in range(hdr + 1, end) if str(ws.cell(r, col["product"]).value or "").strip().upper().startswith("FOC")), None)
    foc = []
    if foc_row:
        for r in range(foc_row + 1, end):
            nm = s_(ws.cell(r, col["product"]).value)
            q = num(ws.cell(r, col["qty"]).value) if "qty" in col else None
            if nm and q:
                foc.append({"name": nm, "qty": q, "unit_price": num(ws.cell(r, col["price"]).value) if "price" in col else None})
        end = foc_row
    items, cur = [], None
    flags = []
    for r in range(hdr + 1, end):
        b = s(ws.cell(r, col["product"]).value)
        lcell = ws.cell(r, col["sizes"]).value
        desc_here = s(ws.cell(r, col["desc"]).value) if "desc" in col else None
        has_line = desc_here and ((num(ws.cell(r, col["price"]).value) if "price" in col else None) is not None or (num(ws.cell(r, col["qty"]).value) if "qty" in col else None) is not None)
        if b or has_line:
            b = b or desc_here
            cur = {"style_no": re.sub(r"\s*-\s*", "-", b), "raw_name": b, "description": s(ws.cell(r, col.get("desc", 0) or 1).value) if "desc" in col else None,
                   "quality": s(ws.cell(r, col["quality"]).value) if "quality" in col else None,
                   "pcs_per_box": s(ws.cell(r, col["box"]).value) if "box" in col else None,
                   "unit_price": num(ws.cell(r, col["price"]).value) if "price" in col else None,
                   "total_qty_stated": num(ws.cell(r, col["qty"]).value) if "qty" in col else None,
                   "colour_text": s(ws.cell(r, col["colour"]).value) if "colour" in col else None,
                   "line_total_stated": num(ws.cell(r, col["total"]).value) if "total" in col else None,
                   "sizes": {}, "checks": [], "source_row": r}
            items.append(cur)
        if cur is not None and lcell not in (None, ""):
            if b is None and num(ws.cell(r, col["sizes"] + 1).value) is not None and not SIZE_PAIR.search(str(lcell)):  # vertikal: Groesse | Menge
                cur["sizes"][str(lcell).strip().upper()] = num(ws.cell(r, col["sizes"] + 1).value)
            else:
                cur["sizes"].update(parse_sizes(lcell, cur["checks"], cur["style_no"]))
    for it in items:
        base = sum(it["sizes"].values())
        st = it["total_qty_stated"]
        raw_col = re.sub(r"(?i)^\s*colou?r\s*|assorted|assortment", "", it["colour_text"] or "").strip()
        colours = [c.strip().title() for c in re.split(r"[/&,]", raw_col) if c.strip()] or [None]
        n = len(colours)
        # Bei mehreren Farben gelten die Groessenmengen je Farbe (Gesamtmenge = Farben x Summe) - nur wenn das rechnerisch aufgeht
        per_colour = n > 1 and st is not None and abs(n * base - st) < 0.5
        if per_colour:
            it["variants"] = [{"colour": c, "sizes": dict(it["sizes"])} for c in colours]
            it["total_qty_computed"] = n * base
        else:
            it["variants"] = [{"colour": colours[0] if n == 1 else raw_col or None, "sizes": dict(it["sizes"])}]
            it["total_qty_computed"] = base
            if n > 1:
                it["checks"].append(f"mehrere Farben ('{it['colour_text']}'): Aufteilung je Farbe nicht eindeutig")
        cp = it["total_qty_computed"]
        if st is not None and abs(st - cp) > 0.5:
            it["checks"].append(f"Summe Groessen {cp:g} != Total QTY {st:g}")
        if it["unit_price"] and it["line_total_stated"] is not None:
            calc = it["unit_price"] * (st if st is not None else cp)
            if abs(calc - it["line_total_stated"]) > 1:
                it["checks"].append(f"Preis*Menge {calc:g} != TOTAL {it['line_total_stated']:g}")
        flags += [f"{it['style_no']}: {c}" for c in it["checks"]]
    po_text = next((str(c.value) for row in ws.iter_rows(max_row=3) for c in row if isinstance(c.value, str) and "PURCHASE ORDER" in c.value.upper()), "")
    date_text = next((str(c.value) for row in ws.iter_rows(max_row=3) for c in row if isinstance(c.value, str) and "DATE:" in c.value.upper()), "")
    d = re.search(r"(\d{2})[-./](\d{2})[-./](\d{4})", date_text)
    terms = next((s(ws.cell(c.row + 1, c.column).value) or s(ws.cell(c.row, c.column + 2).value) for row in ws.iter_rows(min_row=hdr) for c in row
                  if isinstance(c.value, str) and c.value.strip().upper().startswith("PAYMENT TERMS")), None)
    total_amt = next((num(ws.cell(c.row, cc).value) for row in ws.iter_rows(min_row=hdr) for c in row if isinstance(c.value, str) and
                      c.value.strip().lower().startswith("total order amount") for cc in range(c.column + 1, c.column + 8) if num(ws.cell(c.row, cc).value) is not None), None)
    sub = next((num(ws.cell(c.row, cc).value) for row in ws.iter_rows(min_row=hdr) for c in row if isinstance(c.value, str) and
                c.value.strip().lower().startswith("subtotal") for cc in range(c.column + 1, c.column + 8) if num(ws.cell(c.row, cc).value) is not None), None)
    pieces = sum(i["total_qty_computed"] for i in items)
    value = sum((i["unit_price"] or 0) * (i["total_qty_stated"] if i["total_qty_stated"] is not None else i["total_qty_computed"]) for i in items)
    if total_amt is not None and abs(value - total_amt) > 1:
        flags.append(f"Summe Positionen {value:g} != Total Order Amount {total_amt:g}")
    return {"layout": "legacy", "purchase_order": {"po_number": re.sub(r"(?i)^\s*purchase order\s*[#.:\s]*", "", po_text).strip() or None,
                                                    "date": f"{d.group(3)}-{d.group(2)}-{d.group(1)}" if d else None,
                                                    "shipment_date": lab(ws, "Shipment Date"), "eta_hamburg": lab(ws, "ETA HAMBURG")},
            "supplier": {"name": lab(ws, "Name:", 11, 17), "address": lab(ws, "Address:", 11, 17), "email": lab(ws, "Email:", 11, 17), "phone": lab(ws, "Phone:", 11, 17)},
            "items": items, "foc_quantities": foc, "totals": {"subtotal": sub, "total_order_amount": total_amt, "sum_positions": value},
            "terms": {"payment_terms_text": terms}, "flags": flags, "stats": {"items": len(items), "pieces": pieces}}


def main(argv):
    root = Path(__file__).parent
    outdir = root / "output" / "po"
    outdir.mkdir(parents=True, exist_ok=True)
    for a in argv:
        f = Path(a)
        try:
            wb = openpyxl.load_workbook(f, data_only=True)
        except Exception as e:
            print(f"! {f.name}: nicht lesbar ({type(e).__name__})")
            continue
        for ws in wb:
            try:
                res = parse_sheet(ws)
            except Exception as e:
                print(f"! {f.name} [{ws.title}]: Fehler {type(e).__name__}: {e}")
                continue
            if not res:
                print(f"- {f.name} [{ws.title}]: Layout nicht erkannt")
                continue
            res["source_file"], res["source_sheet"] = f.name, ws.title
            out = outdir / f"{f.stem}__{ws.title.replace(' ', '_')}.json"
            out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
            print(f"+ {f.name} [{ws.title}]  {res['stats']['items']} Styles, {res['stats']['pieces']:g} Stk, Summe {res['totals']['sum_positions']:g} USD, {len(res['flags'])} Hinweise")


if __name__ == "__main__":
    main(sys.argv[1:])
