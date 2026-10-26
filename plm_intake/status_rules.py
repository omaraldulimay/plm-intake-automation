"""Status-Regeln fuer Bestellungen: belegbare Uebergaenge, NUR LESEN (schreibt nie ins PLM).

Grundsatz: nie nach unten, nie ab Complete, nur nach Beleg im PLM selbst (Sendungen, Zahlungsraten) oder in den Notizen (BELEG-Zeilen).
Zuordnung nur ueber den Lieferanten zaehlt nicht (events.py gibt solche Ereignisse gar nicht erst als Status weiter).

Regeln (Sicherheit):
  SENDUNG_UNTERWEGS   Sendung in_transit/delivered an der Order                         -> In Transit            hoch
  SENDUNG_TRACKING    Sendung pending MIT Tracking-Nummer                                -> In Transit            mittel
  ZAHLUNG_PAID        mindestens eine Rate Paid, Order steht auf Draft/Awaiting Approval  -> Approved              hoch
  BELEG_OHNE_SENDUNG  Rechnung/Packliste (BELEG-Zeile >= 30 Tage alt), keine offene Sendung -> In Transit          mittel
  RECHNUNG_ALS_BASIS  Notiz: Order aus Rechnungen/'gelieferte Menge' angelegt, Quellmail >= 30 Tage, keine offene Sendung -> In Transit mittel
  COMPLETE_BELEGT     alle Sendungen delivered UND alle Raten Paid (Menge >= 98 %)       -> Complete              hoch (sonst mittel)
  COMPLETE_RATEN_OFFEN alle Sendungen delivered, aber Raten offen                       -> Complete (Vorschlag)  niedrig
  EREIGNIS_MEILENSTEIN Produktionsstart/PI/Anzahlung laut Ereignis (direkt zugeordnet)   -> Approved/In Production hoch (schreibt events.py)
Hinweise (kein Vorschlag): Complete mit offenen Raten; Draft ohne belegbaren Uebergang (Platzhalter mit Summe 0 werden nicht gelistet).

  .venv/bin/python -m plm_intake.status_rules        # Dry-Run gegen das echte PLM, schreibt output/phase2/B24/status_freigabe.md/.csv
"""
import csv
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STATUS_ORDER = {"Draft": 1, "Awaiting Approval": 2, "Approved": 3, "In Production": 4, "QC": 5, "In Transit": 6, "Complete": 7}
MIN_BELEG_TAGE = 30
MIN_MENGE_ANTEIL = 0.98
RANK = {"hoch": 3, "mittel": 2, "niedrig": 1}
EVENT_RULE = "EREIGNIS_MEILENSTEIN"
CSV_COLS = ["Nr", "Order-ID", "Order", "Aktuell", "Ziel", "Regel", "Beleg", "Sicherheit", "Art", "Freigabe"]
OUT_DIR = ROOT / "output" / "phase2" / "B24"
TEST = re.compile(r"(?i)(^|[^a-z0-9])zz|(^|[^a-z0-9])T1([^a-z0-9]|$)|TEST")
BELEG = re.compile(r"\[(\d{4}-\d{2}-\d{2})[^\]]*\]\s*BELEG\s+(\w+)\s*:\s*([^\n]{0,120})", re.I)
RECHNUNG_BASIS = re.compile(r"(gelieferte Menge|laut (?:Alpha-)?Rechnung|aus (?:den )?(?:Alpha-)?Rechnungen)", re.I)   # Order wurde aus Rechnungen angelegt = Ware war schon unterwegs
MAIL_VOM = re.compile(r"Mail vom (\d{4}-\d{2}-\d{2})")
BELEG_ART = re.compile(r"invoice|rechnung|packing|packliste", re.I)


def status_name(o):
    s = o.get("status")
    return s.get("status") if isinstance(s, dict) else s


def is_test(o):
    return bool(TEST.search(str(o.get("title") or "")))


def _pay_open(p):
    return str(p.get("status") or "").lower() != "paid"


def shipments_of(shipments, order_id):
    return [s for s in shipments if any(p.get("orderId") == order_id for p in s.get("products") or [])]


def beleg_lines(notes, today):
    """[(datum, art, text)] der Rechnungs-/Packlisten-Belege in den Notizen, die mindestens MIN_BELEG_TAGE alt sind."""
    out = []
    for d, art, txt in BELEG.findall(str(notes or "")):
        if not BELEG_ART.search(art):
            continue
        try:
            age = (today - dt.date.fromisoformat(d)).days
        except ValueError:
            continue
        if age >= MIN_BELEG_TAGE:
            out.append((d, art.upper(), txt.strip()))
    return out


def candidates(o, ships, today, event_to=None):
    """Alle Regeln, die auf die Order zutreffen: [{ziel, regel, beleg, sicherheit}] (auch solche ohne Fortschritt; Filter macht evaluate)."""
    c = []
    pays = o.get("payments") or []
    in_t = [s for s in ships if s.get("status") in ("in_transit", "delivered")]
    pend = [s for s in ships if s.get("status") == "pending"]
    openish = [s for s in ships if s.get("status") in ("pending", "in_transit")]
    if in_t:
        s = in_t[0]
        c.append({"ziel": "In Transit", "regel": "SENDUNG_UNTERWEGS", "sicherheit": "hoch", "beleg": "Sendung '%s' (%s%s)" % (s.get("title"), s.get("status"), ", +%d weitere" % (len(in_t) - 1) if len(in_t) > 1 else "")})
    else:
        trk = [s for s in pend if str(s.get("trackingNumber") or "").strip()]
        if trk:
            c.append({"ziel": "In Transit", "regel": "SENDUNG_TRACKING", "sicherheit": "mittel", "beleg": "Sendung '%s' pending mit Tracking %s" % (trk[0].get("title"), trk[0].get("trackingNumber"))})
    paid = [p for p in pays if not _pay_open(p)]
    if paid:
        p = paid[0]
        c.append({"ziel": "Approved", "regel": "ZAHLUNG_PAID", "sicherheit": "hoch", "beleg": "Rate '%s' %s Paid" % (p.get("name"), p.get("amount"))})
    bl = beleg_lines(o.get("_notes"), today)
    if bl and not openish:
        d, art, txt = bl[-1]
        c.append({"ziel": "In Transit", "regel": "BELEG_OHNE_SENDUNG", "sicherheit": "mittel", "beleg": "Notiz BELEG %s vom %s: %s" % (art, d, txt[:80])})
    notes = str(o.get("_notes") or "")
    m_ = RECHNUNG_BASIS.search(notes)
    if m_ and not openish and not bl:
        try:
            alt = (today - dt.date.fromisoformat(MAIL_VOM.search(notes).group(1))).days >= MIN_BELEG_TAGE
        except (AttributeError, ValueError):
            alt = False
        if alt:
            c.append({"ziel": "In Transit", "regel": "RECHNUNG_ALS_BASIS", "sicherheit": "mittel", "beleg": "Notiz: Order aus Rechnungen angelegt ('%s'), Quellmail %s" % (m_.group(1), MAIL_VOM.search(notes).group(1))})
    if ships and not openish and all(s.get("status") == "delivered" for s in ships):
        total = float(o.get("totalNumberOfPieces") or 0)
        shipped = sum(float(s.get("totalQuantity") or 0) for s in ships)
        if pays and not any(_pay_open(p) for p in pays):
            full = total > 0 and shipped >= MIN_MENGE_ANTEIL * total
            c.append({"ziel": "Complete", "regel": "COMPLETE_BELEGT", "sicherheit": "hoch" if full else "mittel",
                      "beleg": "%d Sendung(en) delivered (%g von %g Stk), alle %d Raten Paid%s" % (len(ships), shipped, total, len(pays), "" if full else " | Menge unter 98 %")})
        else:
            n = len([p for p in pays if _pay_open(p)])
            c.append({"ziel": "Complete", "regel": "COMPLETE_RATEN_OFFEN", "sicherheit": "niedrig",
                      "beleg": "%d Sendung(en) delivered, aber %s offen" % (len(ships), "%d Rate(n)" % n if pays else "keine Zahlungsraten erfasst")})
    if event_to:
        c.append({"ziel": event_to["to"], "regel": EVENT_RULE, "sicherheit": "hoch", "beleg": event_to.get("why") or "Ereignis"})
    return c


def evaluate(orders, shipments, today=None, event_status=None):
    """-> Liste von Zeilen {order_id, nr, title, aktuell, ziel, regel, beleg, sicherheit, art, auto}. art: Aenderung | Hinweis.
    event_status: {order_id: {"to": Status, "why": Text}} aus dem Ereignis-Plan (nur direkt zugeordnete Ereignisse)."""
    today = today or dt.date.today()
    rows = []
    for o in orders:
        if is_test(o):
            continue
        cur = status_name(o)
        if cur not in STATUS_ORDER:
            continue
        base = {"order_id": o["id"], "nr": o.get("orderNumber"), "title": o.get("title"), "aktuell": cur}
        ships = shipments_of(shipments, o["id"])
        if cur == "Complete":
            op = [p for p in o.get("payments") or [] if _pay_open(p)]
            if op:
                rows.append(dict(base, ziel=cur, regel="HINWEIS_COMPLETE_RATEN_OFFEN", sicherheit="niedrig", art="Hinweis", auto=False,
                                 beleg="%d von %d Raten nicht Paid (%s)" % (len(op), len(o.get("payments") or []), ", ".join(str(p.get("name")) for p in op[:4]))))
            continue
        cn = STATUS_ORDER[cur]
        c = [x for x in candidates(o, ships, today, (event_status or {}).get(o["id"])) if STATUS_ORDER.get(x["ziel"], 0) > cn]
        if c:
            best = max(c, key=lambda x: (STATUS_ORDER[x["ziel"]], RANK[x["sicherheit"]]))
            # gleiche Zielstufe: hoechste Sicherheit; hoehere Stufe mit niedrigerer Sicherheit ist ein eigener Vorschlag und verdraengt nicht die sichere
            sure = [x for x in c if x["sicherheit"] == "hoch"]
            if sure and RANK[best["sicherheit"]] < RANK["hoch"]:
                top = max(sure, key=lambda x: STATUS_ORDER[x["ziel"]])
                rows.append(dict(base, art="Aenderung", auto=top["regel"] != EVENT_RULE, **top))
                if best["ziel"] != top["ziel"]:
                    rows.append(dict(base, art="Aenderung", auto=False, **best))
            else:
                rows.append(dict(base, art="Aenderung", auto=best["regel"] != EVENT_RULE and best["sicherheit"] == "hoch", **best))
        elif cur == "Draft" and float(o.get("totalCost") or 0) > 0:
            rows.append(dict(base, ziel=cur, regel="HINWEIS_NICHT_BELEGBAR", sicherheit="niedrig", art="Hinweis", auto=False,
                             beleg="kein Beleg fuer einen Uebergang (keine Sendung, keine bezahlte Rate, kein alter Rechnungs-/Packlisten-Beleg)"))
    return rows


def auto_candidates(rows):
    """Aenderungen, die ohne Rueckfrage laufen duerften (Sicherheit hoch, nicht vom Ereignis-Schritt abgedeckt)."""
    return [r for r in rows if r["art"] == "Aenderung" and r["sicherheit"] == "hoch" and r.get("auto")]


def to_csv_row(r):
    return {"Nr": r.get("nr"), "Order-ID": r["order_id"], "Order": r["title"], "Aktuell": r["aktuell"], "Ziel": r["ziel"], "Regel": r["regel"],
            "Beleg": r["beleg"], "Sicherheit": r["sicherheit"], "Art": r["art"], "Freigabe": ""}


def write_csv(rows, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow(to_csv_row(r))


def _tab(rows):
    L = ["| Nr | Order | aktuell | Ziel | Regel | Beleg | auto |", "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: -(x.get("nr") or 0)):
        L.append("| %s | %s | %s | **%s** | %s | %s | %s |" % (r.get("nr"), r["title"], r["aktuell"], r["ziel"], r["regel"], str(r["beleg"]).replace("|", "/"), "ja" if r.get("auto") else "nein"))
    return L


def render_md(rows, platzhalter=0, today=None):
    ch = [r for r in rows if r["art"] == "Aenderung"]
    hi = [r for r in ch if r["sicherheit"] == "hoch"]
    mi = [r for r in ch if r["sicherheit"] == "mittel"]
    lo = [r for r in ch if r["sicherheit"] == "niedrig"]
    cr = [r for r in rows if r["regel"] == "HINWEIS_COMPLETE_RATEN_OFFEN"]
    nb = [r for r in rows if r["regel"] == "HINWEIS_NICHT_BELEGBAR"]
    L = ["# Status-Freigabeliste (Dry-Run, nichts geschrieben)", "", "Stand %s. Regeln: plm_intake/status_rules.py. Nie nach unten, nie ab Complete." % (today or dt.date.today()),
         "Freigabe: CSV `status_freigabe.csv`, Spalte Freigabe mit `ja`/`nein` fuellen, dann `.venv/bin/python -m plm_intake.status_apply output/phase2/B24/status_freigabe.csv` (Dry-Run) bzw. mit `--apply`.", "",
         "Vorschlaege: %d (hoch %d, mittel %d, niedrig %d) | Hinweise: Complete mit offenen Raten %d, nicht belegbar %d | Platzhalter-Drafts (Summe 0) nicht gelistet: %d" % (
             len(ch), len(hi), len(mi), len(lo), len(cr), len(nb), platzhalter), ""]
    L += ["## Hoch: wuerde automatisch laufen (nur mit STATUS_AUTO=1, max. 10 je Lauf)", ""] + (_tab(hi) if hi else ["- keine"]) + [""]
    L += ["## Mittel: Omar waehlt", ""] + (_tab(mi) if mi else ["- keine"]) + [""]
    L += ["## Niedrig: Omar waehlt", ""] + (_tab(lo) if lo else ["- keine"]) + [""]
    L += ["## Hinweis: Complete-Orders mit offenen Raten (kein Statuswechsel, Zahlung klaeren)", ""] + (_tab(cr) if cr else ["- keine"]) + [""]
    L += ["## Hinweis: Draft-Orders ohne belegbaren Uebergang (nichts vorgeschlagen)", ""] + (_tab(nb) if nb else ["- keine"]) + [""]
    return "\n".join(L)


def main(argv=None):
    import plm_client
    from plm_intake.context import fetch_all, add_po_numbers
    orders = fetch_all(plm_client.call, "orders")
    shipments = fetch_all(plm_client.call, "shipments")
    for _ in range(3):   # Notizen per Browser (nur lesen); schlaegt der Browser fehl, wird wiederholt
        add_po_numbers({"orders": orders})
        n = sum(1 for o in orders if o.get("_notes"))
        if n:
            break
    if not n:
        print("WARNUNG: Notizen nicht lesbar, Notiz-Regeln (BELEG_OHNE_SENDUNG) fehlen in dieser Liste")
    rows = evaluate(orders, shipments)
    draft0 = sum(1 for o in orders if not is_test(o) and status_name(o) == "Draft" and float(o.get("totalCost") or 0) <= 0)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "status_freigabe.md").write_text(render_md(rows, draft0))
    write_csv(rows, OUT_DIR / "status_freigabe.csv")
    ch = [r for r in rows if r["art"] == "Aenderung"]
    print("Notizen gelesen fuer %d Orders; Vorschlaege %d (hoch %d, mittel %d, niedrig %d); Hinweise %d" % (
        n, len(ch), *(len([r for r in ch if r["sicherheit"] == s]) for s in ("hoch", "mittel", "niedrig")), len(rows) - len(ch)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
