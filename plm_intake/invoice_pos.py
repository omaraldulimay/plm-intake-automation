"""Batch 11: Bestellungen "laut Rechnung/PO-Datei" aus gepruefeten Phase-2-Extrakten (E2), wenn im PLM noch keine Order existiert.

  python3 -m plm_intake.invoice_pos   -> output/phase2/B11/inbox/*.json (kein PLM-Zugriff); Anlage danach ueber auto_run wie alpha_pos.
  .venv/bin/python -m plm_intake.invoice_pos --lieferant_i [--apply]   -> je eine eigene Order fuer die Lieferant I-Teillieferungen SPR2026000000422/438 (Preise aus dem Beleg-JSON,
      Groessen/Farben aus der Packliste, Summe Stueck und Betrag muessen gegen den Beleg stimmen, sonst keine Anlage). Dry-Run Standard."""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P2 = ROOT / "output" / "phase2"
OUT = P2 / "B11" / "inbox"
JOBS = [  # (Ordner, Extrakt, Lieferant, PO-Nummer, Notiz)
    ("lieferant_al", "att_b9c05e7f98b2", "Lieferant AL", "GE-20260310",
     "laut Rechnung GE-20260310 (Fassung SMILODOX = Summe Luft 23.724 Stk/38.687,75 + See 30.359 Stk/68.567,30); keine PO-Datei vorhanden"),
    ("lieferant_e", "att_ab9917db4d4b", "Lieferant E", "TUR-KUNDE_X-DE-2026-06-25", "laut PO-Datei PO_TUR_KUNDE_X_DE_25.06.2026"),
    ("lieferant_e", "att_77794dc4e6a1", "Lieferant E", "TUR-KUNDE_X-CH-2026-06-25", "laut PO-Datei PO_TUR_KUNDE_X_CH_25.06.2026"),
    ("lieferant_e", "att_8c68f84836c7", "Lieferant E", "TUR-KUNDE_X-LAGER-2026-06-25", "laut PO-Datei PO_TUR_KUNDE_X_LAGER_25.06.2026"),
    ("lieferant_e", "att_e79c820173d1", "Lieferant E", "TUR-XTRAFIT-2026-07-21", "laut PO-Datei PO_TUR_Xtrafit_21.07.2026"),
]


# ---------- Lieferant I-Teillieferungen (Rechnung = eigene Order, Preise aus dem Beleg, Groessen/Farben aus der Packliste) ----------
B21 = P2 / "B21"
LIEFERANT_I = [  # (Mail-ID, Rechnungsnr, Rechnungsdatum, Kolli, Notiz)
    ("1a159e3b788a4764", "SPR2026000000422", "20.10.2026", 1083),
    ("1a168f1c8a9d3d4c", "SPR2026000000438", "23.10.2026", 623),
]
COLOR_FIX = {"SCHWARZ": "Schwarz", "BRAUN": "Braun", "WEIB": "Weiß", "WEISS": "Weiß", "HELLGRAU": "Hellgrau", "HELLBLAU": "Hellblau"}   # 'WEIB' = Schreibfehler der Packliste fuer Weiss
LIEFERANT_I_VENDOR = "Lieferant I"


def _de(n):
    return "{:,}".format(int(n)).replace(",", ".")


def lieferant_i_doc(beleg, packliste, kolli, mail_id):
    """Beleg-JSON (Rechnung) + Packliste {'Style|FARBE': {Groesse: Menge}} -> PO-Dokument fuer core.build.
    Je Style muss die Packlistensumme der Positionsmenge laut Beleg entsprechen (qty bzw. Summe der Variantenmengen/-groessen), sonst ValueError."""
    inv, src = beleg["source"]["doc"], beleg["source"]
    items, tot, pcs = [], 0.0, 0
    for it in beleg["items"]:
        sku = str(it["sku"]).strip()
        v0 = (it.get("variants") or [{}])[0]
        price = float(v0.get("price") or it.get("product_info", {}).get("purchase_price") or 0)
        qty = int(it.get("qty") or sum(int(v.get("quantity") or 0) for v in it["variants"]) or 0)
        if sku == "26504" or "26404" in str(it.get("name")):   # Beleg schreibt im Namen 26404, Style/Packliste 26504 (Jogginghose)
            sku = "26504"
        cols = {k.split("|", 1)[1]: v for k, v in packliste.items() if k.split("|", 1)[0].upper() == sku.upper()}
        if not cols:
            raise ValueError("Style %s nicht in der Packliste" % sku)
        got = sum(sum(v.values()) for v in cols.values())
        if got != qty:
            raise ValueError("Style %s: Packliste %d Stk != Beleg %d Stk" % (sku, got, qty))
        name = re.sub(r"\s*%s\s*$" % re.escape(sku), "", re.sub(r"26404", "26504", str(it.get("name") or ""))).strip() or sku   # Anzeige: '<Style> <Name>' wie bei den anderen Lieferant I-Orders
        order = ["XS", "S", "M", "L", "XL", "2XL", "3XL"]
        variants = []
        for col, sizes in cols.items():
            srt = {k: sizes[k] for k in sorted(sizes, key=lambda z: order.index(z) if z in order else 99)}
            variants.append({"color": COLOR_FIX.get(col.upper(), col.title()), "price": price, "sizes": srt})
        items.append({"sku": sku, "name": name, "variants": variants})
        tot += qty * price
        pcs += qty
    tot = round(tot, 2)
    if pcs != int(beleg["total_pieces"]) or abs(tot - float(beleg["total_cost"])) > 0.01:
        raise ValueError("%s: Positionen %d Stk / %.2f != Beleg %s Stk / %s" % (inv, pcs, tot, beleg["total_pieces"], beleg["total_cost"]))
    date = beleg.get("doc_date")
    pay = {"name": "100% Mal Mukabili (Zahlung gegen Ware)", "status": "Unpaid", "amount": tot, "due": date, "terms": "Mal Mukabili (Zahlung gegen Ware)"}
    return {"doc_type": "PO", "source": {"doc": inv, "mail_id": mail_id, "mail_date": src.get("mail_date")}, "vendor": LIEFERANT_I_VENDOR, "po_number": inv, "doc_date": date,
            "currency": beleg.get("currency") or "EUR", "incoterm": beleg.get("incoterm"), "ship_to": beleg.get("ship_to"), "ex_factory": None, "etd": None, "items": items, "payments": [pay],
            "total_cost": tot, "total_pieces": pcs, "contract_total": None,
            "notes": "Bestellung laut Rechnung %s vom %s (%s Stk / %s %s, %s Kolli); Teillieferung zu Lieferant I-Bestellung 409 (PO-LIEFERANT_I-SPR2026000000409), eigene Order, keine PO-Datei vorhanden. "
                     "Preise laut Rechnung, Groessen und Farben laut Packliste vom Lieferdatum. Zahlung: 100%% Mal Mukabili." % (inv, ".".join(reversed(date.split("-"))), _de(pcs), _de(tot) if tot == int(tot) else ("{:,.2f}".format(tot).replace(",", "X").replace(".", ",").replace("X", ".")), beleg.get("currency") or "EUR", kolli)}


def lieferant_i_docs(inbox=None, packlisten=None):
    """[(Dateiname, doc)] fuer 422 und 438 aus Drive-Inbox (Beleg-JSON <mail>_1.json) und B21/lieferant_i_packlisten.json."""
    from plm_intake.docs_existing import DEFAULT_INBOX
    inbox = Path(inbox or DEFAULT_INBOX)
    pl = json.load(open(packlisten or (B21 / "lieferant_i_packlisten.json")))
    out = []
    for mail_id, inv, _d, kolli in LIEFERANT_I:
        beleg = json.load(open(inbox / (mail_id + "_1.json")))
        out.append((inv + ".json", lieferant_i_doc(beleg, pl[mail_id], kolli, mail_id)))
    return out


def lieferant_i_payload(r):
    """Zahlung ohne Platzhalter-Faelligkeit (Mal Mukabili hat keinen Termin, wie bei #96); der Vermerk 'Zahlungstermin Platzhalter' faellt weg."""
    p = r.payload
    for pay in p["payments"]:
        pay.pop("dueDate", None)
    p["notes"] = re.sub(r"\s*Offen: Zahlungstermin Platzhalter: [^.;]*\.?", "", p["notes"]).strip()
    return p


def lieferant_i_run(apply=False, inbox=None, ctx=None):
    import copy
    from plm_intake import core
    docs = lieferant_i_docs(inbox)
    if ctx is None:
        from plm_intake.context import load_context, add_po_numbers
        ctx = load_context()
        add_po_numbers(ctx)
    ctx["aliases"] = {}
    ctx = copy.deepcopy(ctx)
    payloads, lines = [], []
    for name, doc in docs:
        r = core.build(doc, ctx, force_create=True)   # Omar hat CREATE entschieden (Style-Ueberschneidung mit #96 ist gewollt)
        bad = [i for i in r.issues if i.level == "ERROR" or i.code in ("sum_mismatch", "pieces_mismatch", "payment_sum")]
        lines.append("%s: %s, %s Stk / %s | %s" % (name, r.decision, r.stats.get("pieces"), r.stats.get("total"), "; ".join("%s %s" % (i.level, i.msg) for i in r.issues if i.level in ("ERROR", "WARN"))[:400]))
        if r.decision != "CREATE" or bad:
            lines.append("  -> NICHT angelegt (Klaerfall)")
            continue
        payloads.append(lieferant_i_payload(r))
        ctx["orders"].append({"id": "pending:" + name, "title": r.payload["title"], "poNumber": r.payload["poNumber"], "manufacturer": {"id": r.payload["manufacturer"]},
                              "totalCost": r.payload["totalCost"], "totalNumberOfPieces": r.payload["totalNumberOfPieces"]})
    print("\n".join(lines))
    res = None
    if apply and payloads:
        from plm_intake import run
        from plm_intake.auto_run import browser
        js = ROOT / "output" / "intake" / "run_lieferant_i_teile.js"
        js.write_text(run.make_js(payloads, False))
        res = None
        for versuch in range(8):   # Profil-Lock (anderer Browser-Lauf): Start scheitert vor jedem Schreiben, nach 20 s erneut versuchen
            try:
                res = browser(js)
                break
            except SystemExit as e:
                if "rocessSingleton" not in str(e) or versuch == 7:
                    raise
                time.sleep(20)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        if any(x.get("error") or x.get("fatal") or x.get("unsure") for x in res):
            raise SystemExit("ABBRUCH: unsicheres Ergebnis, per REST nach Titel pruefen, nichts wiederholen")
    return payloads, res


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):
        f.unlink()
    for folder, fid, vendor, po, note in JOBS:
        d = json.load(open(P2 / folder / "extract" / (fid + ".json")))
        o, inv = d.get("order") or {}, d.get("invoice") or {}
        items, tot, pcs = [], 0.0, 0   # Positionen ohne Preis (0) werden trotzdem angelegt: core.build vermerkt 'PREIS AUSSTEHEND', price_fill traegt den Preis spaeter nach
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
    return 0


if __name__ == "__main__":
    if "--lieferant_i" in sys.argv:
        pl, _ = lieferant_i_run("--apply" in sys.argv)
        print("%d Orders %s" % (len(pl), "angelegt" if "--apply" in sys.argv else "geplant (Dry-Run)"))
        sys.exit(0)
    sys.exit(main())
