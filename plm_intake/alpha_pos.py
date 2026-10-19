"""Lieferant A-Bestellungen (ALP-53..58-25 FIT-X, ALP-336..352-25 NOS) aus den gelesenen Alpha-Rechnungen (output/phase2/alpha/extract) als Inbox-Bestelldateien bauen.

  python3 -m plm_intake.alpha_pos        schreibt output/phase2/alpha/inbox_pos/*.json + bericht (KEIN PLM-Zugriff); danach auto_run Trockenlauf/--apply wie bei den anderen Phase-2-Bestellungen.

Regeln: PO-Menge = Summe der Rechnungspositionen mit dieser Alpha-PO-Referenz (= bisher gelieferte Menge); Preis aus der Rechnung; HD-Codes werden auf die SNM/SNW26-Codes abgebildet
(Zuordnung output/phase2/alpha/zuordnung_ergebnis.md); keine Zahlungsraten (kein Beleg). Nicht angelegt: ALP-353/355/357/396 (= vorhandene PLM-Orders #54/#53), ALPHA-195-24 (2024), Positionen ohne PO-Referenz."""
import collections
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "output" / "phase2" / "alpha"
OUT = A / "inbox_pos"

STYLE_MAP = {"HD189": "SNM26-006", "HD116": "SNW26-005", "HD67": "SNM26-004", "HD99": "SNM26-001", "HD109": "SNM26-008", "MP21": "SNM26-003",
             "HD81": "SNW26-008", "FXHD81": "SNW26-008", "HD82": "SNW26-004", "FXHD82": "SNW26-004", "ALP_60-25": "SNW26-003"}
WANT = {"ALP-%d-25" % n for n in (53, 54, 55, 56, 57, 58, 336, 337, 338, 339, 340, 341, 342, 343, 345, 346, 347, 348, 352)}
SKIP_EXISTING = {"ALP-353-25", "ALP-355-25", "ALP-357-25", "ALP-396-25"}


def norm_ref(r):
    m = re.search(r"AL(?:PHA|P)[-_ ]?(\d+)[-_ ](\d\d)", str(r or "").upper())
    return "ALP-%s-%s" % (m.group(1), m.group(2)) if m else None


def norm_style(s):
    k = re.sub(r"[ \-]", "", str(s or "").upper())
    if str(s) in STYLE_MAP:
        return STYLE_MAP[str(s)]
    return STYLE_MAP.get(k) or (re.sub(r"\s+", "", str(s)) if str(s).upper().startswith(("SNM", "SNW")) else str(s))


def norm_size(z):
    z = str(z).upper().replace("XXXL", "3XL").replace("XXXXL", "4XL")
    return {"XXL": "2XL"}.get(z, z)


def build():
    pos = collections.defaultdict(lambda: {"inv": {}, "lines": collections.defaultdict(lambda: collections.defaultdict(int)), "pc": collections.defaultdict(float)})
    for f in sorted(glob.glob(str(A / "extract" / "*.json"))):
        d = json.load(open(f))
        if "invoice" not in d:
            continue
        inv = d["invoice"] or {}
        for it in (d["order"] or {}).get("items") or []:
            ref = norm_ref(it.get("po_ref"))
            if not ref or ref not in WANT:
                continue
            p = pos[ref]
            p["inv"][inv.get("nr")] = (inv.get("datum_iso") or inv.get("datum"), (d.get("quelle") or {}).get("name"), d["fileId"])
            style = norm_style(it.get("style"))
            key = (style, str(it.get("color") or "").title(), float(it.get("price")))
            for s, q in (it.get("sizes") or {}).items():
                p["lines"][key][norm_size(s)] += int(q)
            p["pc"][key] += float(it.get("qty") or 0)
    return pos


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    pos = build()
    rep = ["# Alpha-Bestellungen aus Rechnungen (gebaut, noch nicht im PLM)", ""]
    problems = 0
    for ref in sorted(pos, key=lambda r: (int(r.split("-")[2]), int(r.split("-")[1]))):
        p = pos[ref]
        items, tot, pcs, remainders = [], 0.0, 0, []
        for (style, color, price), sizes in sorted(p["lines"].items()):
            qty = sum(sizes.values())
            diff = int(round(p["pc"][(style, color, price)] - qty))
            if diff > 0:   # Packliste unvollstaendig: Rechnungsmenge ist verbindlich, Rest als ONE SIZE (Platzhalter wie bei frueheren POs)
                sizes = dict(sizes); sizes["ONE SIZE"] = diff; qty += diff
                rep.append("- Hinweis %s %s: %d Stk ohne Groessenangabe als ONE SIZE (Rechnungsmenge verbindlich)" % (ref, style, diff))
                remainders.append("%s %d Stk ohne Groessenangabe als ONE SIZE" % (style, diff))
            elif diff < 0:
                rep.append("- ACHTUNG %s %s: Groessensumme %d > Rechnungsmenge %d" % (ref, style, qty, p["pc"][(style, color, price)]))
                problems += 1
            items.append({"sku": style, "name": style, "variants": [{"color": color, "price": price, "sizes": dict(sizes)}]})
            tot += qty * price
            pcs += qty
        dates = sorted(v[0] for v in p["inv"].values() if v[0])
        dd = lambda s: ("%s-%s-%s" % (s[6:], s[3:5], s[:2])) if s and re.match(r"\d\d\.\d\d\.\d{4}", s) else s
        first = dd(dates[0]) if dates else None
        nr = sorted(p["inv"])
        d = {"doc_type": "PO", "source": {"doc": "Alpha-Rechnungen %s" % ", ".join(str(x) for x in nr), "mail_id": None, "mail_date": first}, "vendor": "Lieferant A",
             "po_number": ref, "doc_date": first, "currency": "USD", "incoterm": "FOB Karachi", "ex_factory": None, "etd": None, "items": items, "payments": [],
             "total_cost": round(tot, 2), "total_pieces": pcs, "contract_total": None,
             "notes": "Phase 2 (aus Alpha-Rechnungen, keine PO-Datei vorhanden): Menge = bisher gelieferte Menge laut Rechnungen %s, Preise aus den Rechnungen. HD-Codes (FIT-X) auf SNM/SNW26-Artikel abgebildet. Keine Zahlungsraten (kein Beleg). Datum = erste Rechnung.%s" % (", ".join(str(x) for x in nr), (" " + "; ".join(remainders) + ".") if remainders else "")}
        (OUT / ("%s.json" % ref)).write_text(json.dumps(d, ensure_ascii=False, indent=1))
        rep.append("- %s: %d Pos., %d Stk, %.2f USD, Rechnungen %s" % (ref, len(items), pcs, tot, ", ".join(str(x) for x in nr)))
    missing = sorted(WANT - set(pos))
    rep += ["", "Ohne Rechnungsposition (nicht gebaut): %s" % (", ".join(missing) or "-"), "Bewusst nicht gebaut (vorhandene PLM-Orders): %s" % ", ".join(sorted(SKIP_EXISTING)), "Warnungen: %d" % problems]
    (A / "inbox_pos_bericht.md").write_text("\n".join(rep))
    print("\n".join(rep))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
