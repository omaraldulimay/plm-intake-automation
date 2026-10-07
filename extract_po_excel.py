#!/usr/bin/env python3
"""Liest Smilodox-PO-Excel-Dateien (Vorlage "Fashion PO Template") deterministisch aus.

Kein Vision/OCR noetig: die Zellen werden direkt gelesen. Jedes Feld wird als
{"value", "confidence", "status", "source"} ausgegeben:
  ok       Wert steht eindeutig in der Zelle (confidence 1.0)
  tbc      Platzhalter wie TBC/DRAFT/leer-nach-Label, Wert bleibt leer
  missing  Feld ist in der Datei nicht befuellt
Rechenpruefungen (Summen) landen unter "checks" - es wird nichts korrigiert.

Aufruf:  .venv/bin/python extract_po_excel.py [scans/datei.xlsx ...]
Ohne Argumente werden alle scans/*.xlsx mit PO-Vorlage verarbeitet.
Ausgabe: output/po/<datei>__<blatt>.json
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

PLACEHOLDER = re.compile(r"^\s*(tbc|tbd|draft|n/?a|-+)?\s*$", re.I)


def rec(value, source=None, status=None):
    """Feld-Datensatz. Platzhalter -> value None, status tbc."""
    if isinstance(value, str):
        value = value.strip()
    if value in (None, ""):
        return {"value": None, "confidence": 0.0, "status": status or "missing", "source": source}
    if isinstance(value, str) and PLACEHOLDER.match(value):
        return {"value": None, "confidence": 0.0, "status": "tbc", "source": source, "raw": value}
    return {"value": value, "confidence": 1.0, "status": status or "ok", "source": source}


def cells(ws):
    """Alle nicht-leeren Zellen als (row, col, wert-als-text)."""
    out = []
    for row in ws.iter_rows():
        for c in row:
            if c.value not in (None, ""):
                out.append((c.row, c.column, c.value, c.coordinate))
    return out


def txt(v):
    return str(v).strip() if v is not None else ""


def find(allc, pred):
    for r, c, v, coord in allc:
        if isinstance(v, str) and pred(v):
            return r, c, v, coord
    return None


def right_of(ws, r, c, max_cols=30):
    """Naechste nicht-leere Zelle rechts von (r, c)."""
    for cc in range(c + 1, c + max_cols):
        v = ws.cell(r, cc).value
        if v not in (None, ""):
            return v, ws.cell(r, cc).coordinate
    return None, None


def labelled(allc, ws, label, exact=True):
    hit = find(allc, lambda v: v.strip().lower() == label.lower() if exact else v.strip().lower().startswith(label.lower()))
    if not hit:
        return rec(None)
    r, c, _, _ = hit
    v, coord = right_of(ws, r, c)
    return rec(v, coord)


def inline(allc, prefix):
    """Zellen wie 'DATE: 09-09-2026' oder 'Shipment Date: TBC'."""
    hit = find(allc, lambda v: v.strip().lower().startswith(prefix.lower()))
    if not hit:
        return rec(None)
    val = re.sub(rf"^\s*{re.escape(prefix)}\s*[:.#]*\s*", "", hit[2], flags=re.I)
    return rec(val, hit[3])


def to_iso(rec_):
    v = rec_["value"]
    if isinstance(v, str):
        for fmt in ("%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
            try:
                rec_["value"] = datetime.strptime(v, fmt).date().isoformat()
                return rec_
            except ValueError:
                pass
        rec_["status"], rec_["confidence"] = "check", 0.5
    return rec_


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def parse_payment_terms(text):
    ms = []
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*%\s*(.*?)(?=\d+(?:[.,]\d+)?\s*%|$)", text or "", flags=re.S):
        pct, rest = float(m.group(1).replace(",", ".")), m.group(2).strip(" ,;.")
        days = re.search(r"(\d+)\s*days", rest, re.I)
        low = rest.lower()
        if "deposit" in low or "before production" in low:
            trigger = "before_production"
        elif days and "after" in low:
            trigger = "after_shipment"
        elif "shipment" in low or "shipping" in low:
            trigger = "at_shipment"
        else:
            trigger = "unknown"
        ms.append({"percent": pct, "text": rest, "trigger": trigger, "days": int(days.group(1)) if days else None})
    total = sum(m["percent"] for m in ms)
    return ms, total


def parse_sheet(ws):
    allc = cells(ws)
    hdr = find(allc, lambda v: v.strip().upper() == "PRODUCT NAME")
    if not hdr:
        return None
    r_h = hdr[0]

    po = {}
    po_hit = find(allc, lambda v: v.strip().upper().startswith("PURCHASE ORDER"))
    po["po_number"] = rec(re.sub(r"(?i)^\s*purchase order\s*[#.:\s]*", "", po_hit[2]) if po_hit else None, po_hit[3] if po_hit else None)
    pn = po["po_number"]
    if pn["value"] and re.match(r"(?i)^(tbc|tbd|draft)\b", pn["value"]):  # z.B. "DRAFT-KLQ2-..." = noch keine offizielle PO-Nr.
        po["po_number"] = {"value": None, "confidence": 0.0, "status": "tbc", "source": pn["source"], "raw": pn["value"]}
    po["date"] = to_iso(inline(allc, "DATE"))
    po["shipment_date"] = inline(allc, "Shipment Date")
    po["eta_hamburg"] = inline(allc, "ETA HAMBURG")

    buyer = {}
    for key, prefix in [("email", "Email:"), ("tel", "Tel.:"), ("eori", "EORI NR.:"), ("tax_id", "Tax ID:")]:
        hit = find([x for x in allc if x[0] < 11], lambda v, p=prefix: v.strip().startswith(p))
        buyer[key] = rec(hit[2].split(":", 1)[1] if hit else None, hit[3] if hit else None)
    buyer["name"] = rec(ws["B3"].value, "B3")
    buyer["address"] = rec(", ".join(txt(ws[f"B{r}"].value) for r in (4, 5) if ws[f"B{r}"].value), "B4:B5")

    sup_rows = [x for x in allc if 11 <= x[0] < r_h]
    supplier = {
        "name": labelled(sup_rows, ws, "Name:"),
        "address": labelled(sup_rows, ws, "Address:"),
        "email": labelled(sup_rows, ws, "Email:"),
        "phone": labelled(sup_rows, ws, "Phone:"),
    }

    # --- Spalten aus Kopfzeile ---
    col = {}
    for r, c, v, _ in allc:
        if r == r_h and isinstance(v, str):
            k = " ".join(v.upper().split())
            if k == "PRODUCT NAME": col["product"] = c
            elif k == "DESCRIPTION": col["description"] = c
            elif k == "QUALITY": col["quality"] = c
            elif k == "VARIANTS": col["variants"] = c
            elif k in ("PCS PER BOX", "BOX SIZE"): col["pcs_per_box"] = c
            elif k in ("PRICE", "PRICE USD"): col["price"] = c
            elif k in ("TOTAL QUANTITY", "QTY", "TOTAL QTY"): col["total_qty"] = c
            elif k in ("STYLE WISE QUANTITY", "SIZE WISE QUANTITY"): col["style_qty"] = c
            elif k == "COLOUR": col["colour"] = c
    size_hit = find([x for x in allc if r_h < x[0] <= r_h + 4], lambda v: v.strip().upper() == "COLORS")
    sizes = {}
    if size_hit:
        r_s, c_s = size_hit[0], size_hit[1]
        for cc in range(c_s + 1, col.get("pcs_per_box", c_s + 12)):
            v = ws.cell(r_s, cc).value
            if v not in (None, ""):
                sizes[cc] = txt(v)
    r_start = (size_hit[0] if size_hit else r_h) + 1

    # --- Ende der Positionen ---
    r_end = ws.max_row
    for r, c, v, _ in allc:
        if r >= r_start and isinstance(v, str) and (v.strip().lower().startswith("subtotal") or v.strip().upper() == "TOTAL"):
            r_end = min(r_end, r)

    items, cur = [], None
    for r in range(r_start, r_end):
        b = ws.cell(r, col["product"]).value
        lv = ws.cell(r, col["variants"]).value
        if b not in (None, ""):
            lines = [x.strip() for x in str(b).split("\n") if x.strip()]
            ref = re.search(r"Ref\.?\s*(\S+)", str(b))
            cur = {
                "style_no": rec(lines[0], ws.cell(r, col["product"]).coordinate),
                "supplier_ref": rec(ref.group(1) if ref else None),
                "product_name": rec(" ".join(l for l in lines[1:] if not l.lower().startswith("ref")) or None),
                "_desc_first_line": str(ws.cell(r, col["description"]).value or "").split("\n")[0].strip(),
                "description": rec(ws.cell(r, col["description"]).value, ws.cell(r, col["description"]).coordinate),
                "quality": rec(ws.cell(r, col["quality"]).value, ws.cell(r, col["quality"]).coordinate),
                "pcs_per_box": rec(ws.cell(r, col["pcs_per_box"]).value, ws.cell(r, col["pcs_per_box"]).coordinate) if "pcs_per_box" in col else rec(None),
                "unit_price": rec(ws.cell(r, col["price"]).value, ws.cell(r, col["price"]).coordinate) if "price" in col else rec(None),
                "total_qty_stated": rec(num(ws.cell(r, col["total_qty"]).value), ws.cell(r, col["total_qty"]).coordinate),
                "colours_stated": rec(ws.cell(r, col["colour"]).value, ws.cell(r, col["colour"]).coordinate) if "colour" in col else rec(None),
                "variants": [],
                "checks": [],
            }
            items.append(cur)
        if cur is not None and lv not in (None, ""):
            vl = [x.strip() for x in str(lv).split("\n") if x.strip()]
            qty = {s: num(ws.cell(r, cc).value) for cc, s in sizes.items() if num(ws.cell(r, cc).value) is not None}
            stated = num(ws.cell(r, col["style_qty"]).value) if "style_qty" in col else None
            cur["variants"].append({
                "colour": rec(vl[0], ws.cell(r, col["variants"]).coordinate),
                "supplier_variant_code": rec(" ".join(vl[1:]) or None),
                "sizes": qty,
                "qty_sum_sizes": sum(qty.values()),
                "qty_stated": stated,
            })

    for it in items:
        first = it.pop("_desc_first_line")
        if it["product_name"]["value"] is None and first:  # EasyFitness-Layout: Name steht in der Beschreibung
            it["product_name"] = rec(first, it["description"]["source"])
        s = sum(v["qty_sum_sizes"] for v in it["variants"])
        for v in it["variants"]:
            if v["qty_stated"] is not None and v["qty_stated"] != v["qty_sum_sizes"]:
                it["checks"].append(f"Variante {v['colour']['value']}: Summe Groessen {v['qty_sum_sizes']:g} != angegebene Menge {v['qty_stated']:g}")
        t = it["total_qty_stated"]["value"]
        if t is not None and t != s:
            it["checks"].append(f"Gesamtmenge angegeben {t:g} != Summe Varianten {s:g}")
        it["total_qty_computed"] = s

    # --- Preise / Summen ---
    totals = {}
    for key, label in [("subtotal", "Subtotal"), ("discount_pct", "Discount"), ("other_cost", "Other Cost"),
                       ("shipping_handling", "Shipping & Handling"), ("total_order_amount", "Total Order Amount")]:
        hit = find([x for x in allc if x[0] >= r_end], lambda v, l=label: v.strip().lower().startswith(l.lower()))
        if hit:
            val, coord = right_of(ws, hit[0], hit[1], 8)
            totals[key] = rec(val, coord or hit[3])
            totals[key]["label"] = hit[2].strip()
        else:
            totals[key] = rec(None)

    # --- Textbloecke ---
    labels = ["DELIVERY, SHIPPING & DOCUMENTS", "PACKING INSTRUCTIONS:", "PAYMENT TERMS:", "Addresses", "BANK ADRESSES", "ADDITIONAL NOTES:"]
    rows = [x for x in allc if x[0] >= r_end]
    secs, key = {}, None
    for r, c, v, coord in sorted(rows):
        s = txt(v)
        match = next((l for l in labels if s.upper().startswith(l.upper())), None)
        if match:
            key = match
            secs.setdefault(key, [])
        elif key and not s.lower().startswith(("smilodox-signature", "supplier-signature")):
            secs[key].append((s, coord))
    block = lambda k: rec(" ".join(t for t, _ in secs.get(k, [])) or None, secs[k][0][1] if secs.get(k) else None)
    delivery = block("DELIVERY, SHIPPING & DOCUMENTS")
    terms = {
        "incoterm": rec(re.search(r"Incoterms?:\s*([A-Z]{3})", delivery["value"] or "").group(1) if re.search(r"Incoterms?:\s*([A-Z]{3})", delivery["value"] or "") else None),
        "documents_required": delivery,
        "packing_instructions": block("PACKING INSTRUCTIONS:"),
        "payment_terms_text": block("PAYMENT TERMS:"),
        "port_of_destination": rec(re.sub(r"(?i)^port of destination:\s*", "", " ".join(t for t, _ in secs.get("Addresses", []))) or None),
        "bank_details": block("BANK ADRESSES"),
        "additional_notes": block("ADDITIONAL NOTES:"),
    }
    ms, pct_total = parse_payment_terms(terms["payment_terms_text"]["value"])
    terms["payment_milestones"] = {"value": ms, "confidence": 1.0 if ms and abs(pct_total - 100) < 0.01 else 0.5,
                                   "status": "ok" if ms and abs(pct_total - 100) < 0.01 else "check", "percent_total": pct_total}

    flags = []
    if po["po_number"]["status"] != "ok": flags.append("PO-Nummer fehlt oder ist Platzhalter (DRAFT/TBC)")
    if not terms["bank_details"]["value"]: flags.append("Bankdaten leer")
    if all(it["unit_price"]["value"] is None for it in items): flags.append("Keine Einzelpreise in den Positionen")
    if totals["total_order_amount"]["value"] is None: flags.append("Gesamtbetrag leer")
    for k in ("shipment_date", "eta_hamburg"):
        if po[k]["status"] != "ok": flags.append(f"{k} noch offen (TBC)")
    for it in items:
        for ch in it["checks"]: flags.append(f"{it['style_no']['value']}: {ch}")

    return {"purchase_order": po, "buyer": buyer, "supplier": supplier, "items": items,
            "totals": totals, "terms": terms, "flags": flags,
            "stats": {"items": len(items), "variants": sum(len(i["variants"]) for i in items),
                      "pieces": sum(i["total_qty_computed"] for i in items)}}


def main(argv):
    root = Path(__file__).parent
    files = [Path(a) for a in argv] or sorted((root / "scans").glob("*.xlsx"))
    outdir = root / "output" / "po"
    outdir.mkdir(parents=True, exist_ok=True)
    for f in files:
        try:
            wb = openpyxl.load_workbook(f, data_only=True)
        except Exception as e:
            print(f"! {f.name}: nicht lesbar ({type(e).__name__}: {e})")
            continue
        for ws in wb:
            try:
                res = parse_sheet(ws)
            except Exception as e:
                print(f"! {f.name} [{ws.title}]: Layout nicht erkannt ({type(e).__name__}: {e}), uebersprungen")
                continue
            if not res:
                print(f"- {f.name} [{ws.title}]: keine PO-Vorlage erkannt, uebersprungen")
                continue
            res["source_file"], res["source_sheet"] = f.name, ws.title
            out = outdir / f"{f.stem}__{ws.title.replace(' ', '_')}.json"
            out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
            s = res["stats"]
            print(f"+ {f.name} [{ws.title}] -> {out.relative_to(root)}  ({s['items']} Styles, {s['variants']} Varianten, {s['pieces']:g} Stueck, {len(res['flags'])} Hinweise)")


if __name__ == "__main__":
    main(sys.argv[1:])
