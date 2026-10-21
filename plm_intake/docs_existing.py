"""Belege zu BESTEHENDEN Bestellungen (Rechnung, Packliste, neue PI-Fassung, Reorder-Verdacht) -> Verlaufszeilen in den Notes der Order.

  python3 -m plm_intake.docs_existing [--inbox DIR] [--ctx ctx.json] [--overrides overrides.json] [--out DIR]
Schreibt NICHTS ins PLM. Erzeugt je Beleg eine Ereignis-Datei (Format wie Inbox/*_events.json) in <out>/doc_events/, die danach der normale Ereignis-Lauf
(plm_intake.events_run --inbox <out>/doc_events) per Browser-Skript einpflegt (wiederholbar, Marker, nur Notes). Bericht: <out>/docs_existing_report.md.

Regeln (wie im Konzept): Eine PO = eine Bestellung mit allen Zahlungen. Rechnung/Packliste/Teillieferung -> Notes der Gesamt-PO. Neue PI-Fassung mit anderer Summe ->
nur Notiz + "Mensch prueft" (Mengen/Preise werden nicht automatisch ueberschrieben, nichts wird verkleinert). Reorder-Verdacht (gleiche Styles) -> Mensch entscheidet,
per overrides.json {"<datei>": "NOTE" | "CREATE" | "SKIP"}: NOTE = nur Notiz an die vorhandene PO, CREATE = neue PO (geht dann ueber case_from_po/case_run), SKIP = ignorieren.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402

DEFAULT_INBOX = Path.home() / "Library/CloudStorage/kontakt@firma.example/Meine Ablage/Inbox"


def _fmt(n):
    return ("%.2f" % n).rstrip("0").rstrip(".") if isinstance(n, (int, float)) else str(n)


def classify(name, po, r, overrides):
    """-> (kind, parent_order_id) kind: SKIP | DELIVERY_DOC | PI_CHANGED | REORDER_QUESTION | NONE"""
    codes = {i.code for i in r.issues}
    ov = (overrides or {}).get(name)
    if ov == "SKIP": return "SKIP", r.existing_id
    if "duplicate" in codes: return "SKIP", r.existing_id
    if "delivery_document_only" in codes and r.existing_id: return "DELIVERY_DOC", r.existing_id
    if "delivery_document_only" in codes: return "ORPHAN_DOC", None   # Beleg, aber die Bestell-PO fehlt im PLM: erst PI/PO anlegen
    if "exists_changed" in codes: return "PI_CHANGED", r.existing_id
    if "style_overlap" in codes:
        return ("DELIVERY_DOC" if ov == "NOTE" else "REORDER_QUESTION"), r.existing_id
    if r.decision == "BLOCK": return "OTHER_BLOCK", r.existing_id
    return "NONE", None


def shipments_pkg(po):
    from plm_intake import shipments
    return shipments.is_packaging_doc(po)


def make_event(name, po, kind, parent, r, today):
    src = po.get("source") or {}
    dtp = str(po.get("doc_type") or "DOC").upper()
    tot, pcs, cur = po.get("total_cost"), po.get("total_pieces"), po.get("currency") or ""
    facts = ["%s %s" % (dtp, po.get("po_number") or "?")]
    if pcs: facts.append("%s Stk" % _fmt(pcs))
    if tot: facts.append("%s %s" % (_fmt(tot), cur))
    pay = [p for p in po.get("payments") or [] if p.get("amount")]
    if pay: facts.append("Zahlungen: " + ", ".join("%s %s %s" % (p.get("name"), _fmt(p["amount"]), p.get("status")) for p in pay[:4]))
    if kind == "PI_CHANGED":
        facts.append("NEUE FASSUNG, Summe/Stueckzahl weicht vom PLM ab: " + "; ".join(i.msg for i in r.issues if i.code == "exists_changed")[:250])
    note = re.sub(r"\s+", " ", str(po.get("notes") or "")).strip()[:260]
    if kind == "DELIVERY_DOC" and shipments_pkg(po):
        facts.insert(0, "Verpackungs-/Etikett-Freigabe (kein Versandbeleg)")
    summary = ": ".join(x for x in [" | ".join(facts), note] if x)
    etype = "SHIPMENT" if dtp == "PACKING_LIST" else "PAYMENT" if dtp == "INVOICE" else "ORDER_CHANGE"   # PI/PO zu bestehender Order = Bestell-Aenderung/Zusatz
    ev = {"type": etype, "vendor": po.get("vendor"), "ref": {"po_number": parent.get("poNumber") or parent.get("title"), "style": None, "container": None},
          "date": None, "summary": summary, "details": {"doc_type": dtp, "paid": False}, "confidence": 0.9,
          "action_needed": "Mengen/Preise im PLM gegen neue Fassung pruefen" if kind == "PI_CHANGED" else None,
          "key": "doc:%s:%s:%s" % (name, po.get("po_number"), dtp)}
    return {"mail_id": src.get("mail_id") or name, "mail_date": src.get("mail_date") or today, "events": [ev]}


class _R:
    issues = []
    decision = "BLOCK"
    existing_id = None


def parent_for(vendor, po, orders, ctx):
    """Eltern-Order eines Belegs: (1) PO-Nr (core.find_parent), (2) Vertragsnummer als Anfang der Beleg-Nr im Titel (min. 8 Zeichen), (3) EINZIGE Order des Lieferanten
    mit gleichem Style. Mehrere Kandidaten -> (None, [Titel]) = Mensch entscheidet. Keine Kandidaten -> (None, [])."""
    vid = vendor["id"]
    p = core.find_parent(vid, po.get("po_number"), orders)
    if p: return p, []
    mine = [o for o in orders if (o.get("manufacturer", {}).get("id") if isinstance(o.get("manufacturer"), dict) else o.get("manufacturer")) == vid]
    pn = core.norm(po.get("po_number"))
    by_id = {x["id"]: x.get("sku") for x in ctx.get("products") or [] if x.get("sku")}
    wanted = set()
    if po.get("items"):
        wanted = {core.norm(i.get("sku")) for i in po["items"] if i.get("sku")}
        for i in po["items"]:
            wanted |= core.style_tokens(i.get("name"))
        wanted.discard("")

    def by_style(cands):   # Orders, deren Produkte/Positionen sich mit den Styles des Belegs ueberlappen
        out = []
        for o in cands:
            theirs = core.order_styles(o, by_id)
            if any(m in theirs or any(len(t) >= 5 and (m.startswith(t) or t.startswith(m)) for t in theirs) for m in wanted): out.append(o)
        return out

    if len(pn) >= 8:
        for k in range(len(pn), 7, -1):
            hit = [o for o in mine if pn[:k] in core.norm(o.get("title"))]
            if len(hit) == 1: return hit[0], []
            if len(hit) > 1:   # Vertragsnummer passt zu mehreren Orders (z. B. Nachbestellungen): die Styles des Belegs entscheiden, sonst Mensch
                narrowed = by_style(hit) if wanted else []
                if len(narrowed) == 1: return narrowed[0], []
                return None, [o["title"] for o in (narrowed or hit)[:4]]
    if wanted:
        hits = by_style(mine)
        if len(hits) == 1: return hits[0], []
        if len(hits) > 1: return None, [o["title"] for o in hits[:4]]
    return None, []


def _doc_unit_price(po):
    items = po.get("items") or []
    try:
        if len(items) == 1 and items[0].get("price"): return float(items[0]["price"])
        if len(items) == 1 and po.get("total_cost") and po.get("total_pieces"): return float(po["total_cost"]) / float(po["total_pieces"])
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return 0


def _order_prices(o, po):
    """Preise der Positionen einer Order, deren Name/SKU einen Style des Belegs enthaelt."""
    styles = {core.norm(i.get("sku")) for i in po.get("items") or [] if i.get("sku")}
    styles.discard("")
    out = []
    for it in o.get("items") or []:
        nm = core.norm(it.get("name"))
        if styles and not any(t in nm for t in styles): continue
        for v in it.get("variants") or []:
            out += [a["price"] for a in v.get("amounts") or [] if a.get("price")]
    return out


def narrow_candidates(po, titles, orders):
    """Mehrere passende Orders: genau eine entscheidet (1) die Bestellnummer des Belegs steht in den Notizen nur EINER Kandidaten-Order, (2) der Stueckpreis des Belegs passt (+-1 %) nur zu EINER, (3) nur EINE hat dieselbe Stueckzahl (+-1,5 %; Teillieferung = Mensch). Sonst None (Mensch)."""
    cands = [o for o in orders if o.get("title") in set(titles)]
    if len(cands) < 2: return None
    pn = core.norm(po.get("po_number"))
    if len(pn) >= 6:
        hit = [o for o in cands if pn in core.norm(o.get("notes") or o.get("_notes"))]
        if len(hit) == 1: return hit[0]
    unit = _doc_unit_price(po)   # Stueckpreis des Belegs = Preis genau einer Kandidaten-Order (z. B. Jacke 13,75 USD nur in der Winter-Order, 13,40 in der Nachbestellung)
    if unit:
        hit = [o for o in cands if any(abs(pr - unit) <= 0.01 * unit for pr in _order_prices(o, po))]
        if len(hit) == 1: return hit[0]
    pcs = po.get("total_pieces")
    try: pcs = float(pcs)
    except (TypeError, ValueError): pcs = 0
    if pcs > 0:
        hit = [o for o in cands if o.get("totalNumberOfPieces") and abs(float(o["totalNumberOfPieces"]) - pcs) <= 0.015 * pcs]
        if len(hit) == 1: return hit[0]
    return None


def delivery_doc(name, po, ctx, orders, overrides):
    """Rechnung/Packliste -> (row, Result-Ersatz). Eltern-PO ueber PO-Nr (find_parent) oder eindeutige Style-Ueberlappung beim selben Lieferanten."""
    if (overrides or {}).get(name) == "SKIP": return {"file": name, "kind": "SKIP"}, _R()
    vendor, why = core.match_vendor(po.get("vendor") or "", ctx.get("vendors") or [], ctx.get("aliases"))
    if not vendor: return {"file": name, "kind": "BLOCKER", "why": "Lieferant unbekannt: %s (%s)" % (po.get("vendor"), why)}, _R()
    parent, amb = parent_for(vendor, po, list(orders.values()), ctx)
    if amb and not parent:
        one = narrow_candidates(po, amb, list(orders.values()))
        if one: parent, amb = one, []
    if amb: return {"file": name, "kind": "AMBIGUOUS_DOC", "po": po.get("po_number"), "why": "passt zu mehreren Orders: " + ", ".join(amb)}, _R()
    if parent: return {"file": name, "kind": "DELIVERY_DOC", "pid": parent["id"]}, _R()
    if not po.get("items"): return {"file": name, "kind": "SERVICE_DOC", "po": po.get("po_number"), "why": "keine Warenpositionen (Fracht/Zoll/Spedition)"}, _R()
    return {"file": name, "kind": "ORPHAN_DOC", "po": po.get("po_number")}, _R()


def run(inbox, ctx, overrides, out, today=None, only=None):
    today = today or dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    orders = {o["id"]: o for o in ctx.get("orders") or []}
    rows, ev_files = [], {}
    for f in sorted(Path(inbox).glob("*.json")):
        if f.name.endswith("_events.json") or (only is not None and f.name not in only): continue
        if (overrides or {}).get(f.name) == "CREATE":   # Mensch hat neue PO entschieden: laeuft ueber die Bestell-Anlage (auto_run/run), nicht als Notiz
            rows.append({"file": f.name, "kind": "CREATE_OVERRIDE"}); continue
        try:
            po = json.load(open(f))
            if str(po.get("doc_type") or "").upper() in ("INVOICE", "PACKING_LIST"):
                # Belege haengen an einer BESTEHENDEN Bestellung: Rechnungs-Zahlungen/-Summen/Waehrung/PO-Nr sind hier kein Blocker (Teilzahlung, Packliste ohne Preise)
                row, r = delivery_doc(f.name, po, ctx, orders, overrides)
                if row.get("kind") in ("BLOCKER", "ORPHAN_DOC", "SERVICE_DOC", "SKIP", "AMBIGUOUS_DOC"):
                    rows.append(row); continue
                parent = orders[row["pid"]]; kind = "DELIVERY_DOC"
                ev_files[f.stem] = make_event(f.name, po, kind, parent, r, today)
                rows.append({"file": f.name, "kind": kind, "po": po.get("po_number"), "parent": "#%s %s" % (parent.get("orderNumber"), parent.get("title")), "pid": parent["id"],
                             "doc_type": str(po.get("doc_type") or "").upper(), "doc": po}); continue
            r = core.build(po, ctx)
        except Exception as e:
            rows.append({"file": f.name, "kind": "FEHLER", "why": "%s: %s" % (type(e).__name__, e)}); continue
        if any(i.level == "ERROR" and i.code not in ("product_unlinked",) for i in r.issues) and not r.existing_id:
            rows.append({"file": f.name, "kind": "BLOCKER", "why": "; ".join(i.msg for i in r.issues if i.level == "ERROR")[:160]}); continue
        kind, pid = classify(f.name, po, r, overrides)
        parent = orders.get(pid) if pid else None
        row = {"file": f.name, "kind": kind, "po": po.get("po_number"), "parent": ("#%s %s" % (parent.get("orderNumber"), parent.get("title"))) if parent else None}
        if kind in ("DELIVERY_DOC", "PI_CHANGED") and parent:
            ev_files[f.stem] = make_event(f.name, po, kind, parent, r, today)
        rows.append(row)
    d = Path(out) / "doc_events"; d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*_events.json"): old.unlink()
    for stem, ev in ev_files.items():
        (d / (stem + "_events.json")).write_text(json.dumps(ev, ensure_ascii=False, indent=1))
    return rows, ev_files


def report(rows):
    L = ["# Belege zu bestehenden Bestellungen", "", "| Datei | Art | PO | gehoert zu |", "|---|---|---|---|"]
    for r in rows: L.append("| %s | %s | %s | %s |" % (r["file"], r["kind"], r.get("po") or "-", r.get("parent") or r.get("why") or "-"))
    orphans = [r for r in rows if r["kind"] == "ORPHAN_DOC"]
    if orphans:
        L += ["", "## Beleg ohne Bestell-PO im PLM (erst PI/PO anlegen, dann Beleg zuordnen)"] + ["- %s (%s)" % (r["file"], r.get("po")) for r in orphans]
    svc = [r for r in rows if r["kind"] == "SERVICE_DOC"]
    if svc:
        L += ["", "## Dienstleister-Belege ohne Warenpositionen (Spedition, Zoll): kein PO-Bezug, nur zur Info"] + ["- %s (%s)" % (r["file"], r.get("po")) for r in svc]
    amb = [r for r in rows if r["kind"] == "AMBIGUOUS_DOC"]
    if amb:
        L += ["", "## Beleg passt zu mehreren Orders (Mensch waehlt, per overrides.json oder PO-Nummer im Beleg klaeren)"] + ["- %s (%s): %s" % (r["file"], r.get("po"), r["why"]) for r in amb]
    q = [r for r in rows if r["kind"] == "REORDER_QUESTION"]
    if q:
        L += ["", "## Entscheidung noetig (Reorder oder Teil derselben Bestellung?)", "Per overrides.json: NOTE = nur Notiz an vorhandene PO, CREATE = neue PO, SKIP = ignorieren:"]
        L += ["- %s -> vorhanden: %s" % (r["file"], r["parent"]) for r in q]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=str(DEFAULT_INBOX)); ap.add_argument("--ctx", default=str(ROOT / "output/intake/ctx_snapshot.json"))
    ap.add_argument("--overrides"); ap.add_argument("--out", default=str(ROOT / "output/intake"))
    a = ap.parse_args(argv)
    ctx = json.load(open(a.ctx)); alias = ROOT / "output/intake/vendor_aliases.json"
    ctx["aliases"] = json.load(open(alias)) if alias.exists() else {}
    ov = json.load(open(a.overrides)) if a.overrides else {}
    rows, evs = run(a.inbox, ctx, ov, a.out)
    rep = report(rows); (Path(a.out) / "docs_existing_report.md").write_text(rep); print(rep)
    print("%d Ereignis-Dateien in %s/doc_events" % (len(evs), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
