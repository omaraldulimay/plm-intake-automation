"""Batch 11: Bestellungen "laut Rechnung/PO-Datei" aus gepruefeten Phase-2-Extrakten (E2), wenn im PLM noch keine Order existiert.

  python3 -m plm_intake.invoice_pos   -> output/phase2/B11/inbox/*.json (kein PLM-Zugriff); Anlage danach ueber auto_run wie alpha_pos."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P2 = ROOT / "output" / "phase2"
OUT = P2 / "B11" / "inbox"
JOBS = [  # (Ordner, Extrakt, Lieferant, PO-Nummer, Notiz)
    ("lieferant_al", "att_b9c05e7f98b2", "Lieferant AL", "GE-20260310",
     "laut Rechnung GE-20260310 (Fassung SMILODOX = Summe Luft 23.724 Stk/38.687,75 + See 30.359 Stk/68.567,30); keine PO-Datei vorhanden"),
    ("lieferant_e", "att_ab9917db4d4b", "Lieferant E", "TUR-KUNDE_X-DE-2026-06-25", "laut PO-Datei PO_TUR_KUNDE_X_DE_25.06.2026; Preis fehlt im Beleg (0)"),
    ("lieferant_e", "att_77794dc4e6a1", "Lieferant E", "TUR-KUNDE_X-CH-2026-06-25", "laut PO-Datei PO_TUR_KUNDE_X_CH_25.06.2026; Preis fehlt im Beleg (0)"),
    ("lieferant_e", "att_8c68f84836c7", "Lieferant E", "TUR-KUNDE_X-LAGER-2026-06-25", "laut PO-Datei PO_TUR_KUNDE_X_LAGER_25.06.2026; Preis fehlt im Beleg (0)"),
    ("lieferant_e", "att_e79c820173d1", "Lieferant E", "TUR-XTRAFIT-2026-07-21", "laut PO-Datei PO_TUR_Xtrafit_21.07.2026; Preis fehlt im Beleg (0)"),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):
        f.unlink()
    for folder, fid, vendor, po, note in JOBS:
        d = json.load(open(P2 / folder / "extract" / (fid + ".json")))
        o, inv = d.get("order") or {}, d.get("invoice") or {}
        items, tot, pcs = [], 0.0, 0
        for it in o["items"]:
            sizes = {str(k).upper(): int(v) for k, v in (it.get("sizes") or {}).items() if v}
            q = int(it.get("qty") or 0)
            if sum(sizes.values()) < q:
                sizes["ONE SIZE"] = q - sum(sizes.values())
            price = float(it.get("price") or 0)
            items.append({"sku": {"561873_C": "561873"}.get(it.get("style"), it.get("style")), "name": it.get("name") or it.get("style"), "variants": [{"color": str(it.get("color") or "").title(), "price": price, "sizes": sizes}]})
            tot += q * price; pcs += q
        date = inv.get("datum_iso") or inv.get("datum") or o.get("po_date")
        doc = {"doc_type": "PO", "source": {"doc": fid, "mail_id": None, "mail_date": date}, "vendor": vendor, "po_number": po, "doc_date": date, "currency": o.get("currency") or "USD",
               "incoterm": inv.get("incoterm"), "ex_factory": None, "etd": None, "items": items, "payments": [], "total_cost": round(tot, 2), "total_pieces": pcs, "contract_total": None,
               "notes": "Phase 2 Batch 11: " + note + ". Keine Zahlungsraten ohne Beleg."}
        (OUT / (po + ".json")).write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        print(po, len(items), "Pos", pcs, "Stk", round(tot, 2), "| Beleg:", o.get("pieces"), o.get("total"))


if __name__ == "__main__":
    sys.exit(main())
