"""Bestellung "laut Rechnung" aus einer Inbox-Rechnung ohne Bestell-PO (E2). Baut eine PO-Datei fuer auto_run; kein PLM-Zugriff.

  python3 -m plm_intake.orphan_invoice_po <Inbox-Datei> <Lieferant im PLM> <PO-Nummer> <Ausgabeordner> "<Notiz>"
Positionen = Rechnungs-/Packlisten-Positionen (tatsaechlich verpackte Ware); Zahlungsraten werden NICHT angelegt (nur mit Beleg)."""
import json
import sys
from pathlib import Path


def build(src, vendor, po_number, note):
    d = json.load(open(src))
    po = d.get("po") or (d if isinstance(d, dict) else d[0])
    items, tot, pcs = [], 0.0, 0
    for it in po["items"]:
        variants = []
        for v in it.get("variants") or []:
            sizes = {str(k).upper(): int(x) for k, x in (v.get("sizes") or {}).items() if x}
            price = float(v.get("price") or 0)
            variants.append({"color": str(v.get("color") or "").title(), "price": price, "sizes": sizes})
            q = sum(sizes.values()); tot += q * price; pcs += q
        items.append({"sku": it.get("sku"), "name": it.get("name") or it.get("sku"), "variants": variants})
    src_doc = po.get("source") or {}
    return {"doc_type": "PO", "source": {"doc": src_doc.get("doc"), "mail_id": src_doc.get("mail_id"), "mail_date": src_doc.get("mail_date")}, "vendor": vendor, "po_number": po_number,
            "doc_date": str(src_doc.get("mail_date") or "")[:10], "currency": po.get("currency") or "EUR", "incoterm": po.get("incoterm"), "ex_factory": None, "etd": None,
            "items": items, "payments": [], "total_cost": round(tot, 2), "total_pieces": pcs, "contract_total": None,
            "notes": note + " Keine Zahlungsraten ohne Beleg."}


def main(argv):
    src, vendor, po_number, out, note = argv[:5]
    doc = build(src, vendor, po_number, note)
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / (po_number + ".json")).write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(po_number, len(doc["items"]), "Pos", doc["total_pieces"], "Stk", doc["total_cost"], doc["currency"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
