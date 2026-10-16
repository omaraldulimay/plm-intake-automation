"""Produktions-Ereignisse aus den Mails (Inbox/<MailId>_events.json) ins PLM einpflegen.

Was automatisch passiert (nur bei eindeutiger Zuordnung zu GENAU einer Order):
  - jedes Ereignis wird als Verlaufszeile an die Notes der Order angehaengt: "[JJJJ-MM-TT HH:MM ev:<Hash>] TYP: Text (Mail <Id>)"
    (der Hash macht das Einspielen wiederholbar: eine Zeile wird nie zweimal angehaengt)
  - SCHEDULE mit konkretem neuen Datum (details.new_ex_factory / new_etd) und Konfidenz >= 0.8 -> Datumsfeld der Order, nur wenn die Mail
    neuer ist als alle bereits eingetragenen SCHEDULE-Zeilen
  - PAYMENT mit details.paid == true und genau EINER offenen Zahlung gleichen Betrags -> diese Zahlung auf Paid
Alles andere (Menge/Preis-Aenderungen, Qualitaet, Muster, Versand ohne Order) bleibt bei den Notes bzw. im Bericht "nicht zugeordnet". Nie loeschen.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402

MIN_CONF_DATE = 0.8


def load_events(paths):
    out = []
    for f in paths:
        d = json.load(open(f))
        for e in d.get("events") or []:
            e = dict(e)
            e["_mail"] = {"id": d.get("mail_id"), "date": d.get("mail_date"), "from": d.get("from"), "subject": d.get("subject")}
            out.append(e)
    return out


def marker(e):
    key = e.get("key") or "|".join([str(e.get("type")), str(e.get("date")), str(e.get("summary"))])
    return hashlib.sha1(key.encode()).hexdigest()[:8]


def line(e):
    m = e["_mail"]
    d = str(m.get("date") or "")[:16] or "0000-00-00 00:00"
    summary = re.sub(r"\s+", " ", str(e.get("summary") or "")).strip()
    for pat in core.BANK_PATTERNS:   # Sicherheitsnetz auch hier
        summary = re.sub(pat, "[Bankdaten entfernt]", summary)
    label = e.get("type")
    dtp = (e.get("details") or {}).get("doc_type")
    if dtp:   # Beleg-Zeilen (Rechnung/Packliste/PI) heissen BELEG, nicht PAYMENT/SHIPMENT
        label = "BELEG %s" % dtp
    return "[%s ev:%s] %s: %s (Mail %s)" % (d, marker(e), label, summary[:400], m.get("id"))


# Produktionsprozess (Best Practice): Draft (PI liegt vor) -> Approved (PI bestaetigt/Anzahlung) -> In Production (Fertigung gestartet) -> QC (Endkontrolle) -> In Transit (Ware beim Spediteur/Schiff)
# -> Complete (Wareneingang UND Restzahlung geklaert). Vorwaerts-nur; automatisch nur bis "In Transit", "Complete" bleibt beim Menschen. Meilenstein steht in details.milestone (Auslese).
STATUS_ORDER = {"Draft": 1, "Awaiting Approval": 2, "Approved": 3, "In Production": 4, "QC": 5, "In Transit": 6, "Complete": 7}
MILESTONE_TARGET = {"PI_CONFIRMED": "Approved", "DEPOSIT_PAID": "Approved", "PRODUCTION_STARTED": "In Production", "INSPECTION": "QC", "SHIPPED": "In Transit"}
MIN_CONF_STATUS = 0.8
ORDER_TYPES = ("SCHEDULE", "SHIPMENT", "PAYMENT", "QUALITY", "DELAY", "ORDER_CHANGE")   # Ereignisse, die zu einer Bestellung gehoeren koennen
ACTIVE_NOT = ("Complete",)                                                                # abgeschlossene Orders zaehlen nicht als "laufend"


IDENT_KEYS = ("tracking", "tracking_number", "awb", "hbl", "mbl", "bl", "container", "invoice", "invoice_number", "ref", "reference", "po", "po_number", "order")
CARRIER = re.compile(r"\b(ups|dhl|fedex|tnt|dpd|gls|hermes|schenker|dsv|kuehne|maersk|hapag|cosco|zoll|customs|spedition_b|kontor)\b", re.I)   # Paket-/Spediteure/Zoll: ohne eigene Kennung keine Produktions-Bestellung
TITLE_STOP = {"order", "reorder", "extra", "first", "second", "third", "main", "bulk", "sample", "samples"}


def id_tokens(text):
    """Kennungen (Container, B/L, AWB, Rechnungs-/PO-Nummern) aus Freitext: mindestens 8 Zeichen mit Buchstaben UND Ziffern. Mail-IDs und Marker-Hashes zaehlen nicht."""
    out = set()
    for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9._/\-]{5,}", str(text or "")):
        n = core.norm(t)
        if len(n) >= 8 and re.search(r"[a-z]", n) and re.search(r"\d", n) and not re.fullmatch(r"[0-9a-f]{8}|[0-9a-f]{16}", n):
            out.add(n)
    return out


def order_index(orders, products=None):
    """Pro Order: SKUs der verlinkten Produkte und bekannte Kennungen aus Notizen/PO-Nummer (Container, HBL, Rechnungsnummern ...). Grundlage fuer die Zuordnung ueber Kennung und Style."""
    sku = {p["id"]: core.norm(p.get("sku")) for p in products or [] if p.get("sku")}
    idx = {}
    for o in orders:
        skus = {sku[i["product"]["id"]] for i in o.get("items") or [] if isinstance(i.get("product"), dict) and i["product"].get("id") in sku}
        idx[o["id"]] = {"skus": skus, "idents": id_tokens(o.get("_notes")) | id_tokens(o.get("poNumber"))}
    return idx


def event_tokens(e):
    ref = e.get("ref") or {}
    d = e.get("details") or {}
    toks = id_tokens(" ".join(str(x) for x in (ref.get("container"), ref.get("po_number")) if x))
    for k in IDENT_KEYS:
        if d.get(k) not in (None, "", False):
            toks |= id_tokens(d[k])
    return toks | id_tokens(e.get("summary")) | id_tokens(e.get("source_quote"))


def thread_key(e):
    sub = str((e.get("_mail") or {}).get("subject") or "")
    sub = re.sub(r"^(\s*(re|fwd?|aw|wg|tr)\s*:\s*)+", "", sub, flags=re.I)
    k = re.sub(r"[^a-z0-9]", "", sub.lower())
    return k if len(k) >= 12 else None   # zu kurze/generische Betreffe verbinden nichts


def title_words(o, vendor_name=""):
    """Unterscheidende Woerter im Order-Titel (ohne PO, Lieferantenname, Zahlen und Fuellwoerter)."""
    skip = set(re.findall(r"[a-z0-9]+", str(vendor_name or "").lower())) | TITLE_STOP | {"po"}
    return {w for w in re.findall(r"[a-z]{4,}", str(o.get("title") or "").lower()) if w not in skip}


def find_order(e, orders, vendors, aliases=None, vendor_aliases=None, vendor_only=False, idx=None):
    """Genau eine Order oder None (+ Grund). Zaehlt: PO-Nummer/Titel, Style (Positionsname oder Produkt-SKU), bekannte Kennung (Container/HBL/Rechnungsnr. aus den Notizen).
    Lieferant allein reicht nur schwach und nur bei vendor_only (mehrdeutig sonst)."""
    ref = e.get("ref") or {}
    po = core.norm(ref.get("po_number"))
    hits = []
    # Alias-Tabelle (von Menschen gepflegt): Lieferanten-Nummer -> Order-Titel, z. B. "ISPOB3.429": "PO-LIEFERANT_W-2026-04-29"
    for alias, title in (aliases or {}).items():
        na = core.norm(alias)
        # exakt, oder die Beleg-/Positionsnummer beginnt mit dem Alias und geht nur mit Suffix weiter ('ISPOB3.429-5' zu 'ISPOB3.429'; Mindestlaenge 6 gegen Zufallstreffer)
        if po and (na == po or (len(na) >= 6 and po.startswith(na))):
            hits = [o for o in orders if core.norm(o.get("title")) == core.norm(title)]
            if len(hits) == 1:
                return hits[0], "alias"
            hits = []
    if po and len(po) >= 4:
        for o in orders:
            if po == core.norm(o.get("poNumber")) or core.po_in_title(ref.get("po_number"), o.get("title")):   # Wortgrenze: '...-2' trifft nicht '...-2EXTRA'
                hits.append(o)
    if not hits and ref.get("style"):
        st = core.norm(ref["style"])
        if len(st) >= 4:
            for o in orders:
                if any(st in core.norm(i.get("name")) for i in o.get("items") or []) or (idx and st in idx.get(o["id"], {}).get("skus", ())):
                    hits.append(o)
    if not hits and idx:   # bekannte Kennung (z. B. HBL/Container aus frueheren Notizen derselben Order)
        toks = event_tokens(e)
        if toks:
            hits = [o for o in orders if toks & idx.get(o["id"], {}).get("idents", set())]
    v = None
    if e.get("vendor"):
        v, _ = core.match_vendor(e["vendor"], vendors, vendor_aliases)
    if v and len(hits) > 1:   # Lieferant als Tiebreaker, wenn er die Treffer eindeutig macht
        by_v = [o for o in hits if (o.get("manufacturer") or {}).get("id") == v["id"]]
        if len(by_v) == 1:
            hits = by_v
    if len(hits) > 1:   # laufende Orders bevorzugen: abgeschlossene sind fast nie gemeint
        running = [o for o in hits if _status(o) not in ACTIVE_NOT]
        if len(running) == 1:
            hits = running
    if len(hits) == 1:
        return hits[0], "ok"
    if hits:
        return None, "mehrdeutig: " + ", ".join(o["title"] for o in hits[:5])
    if vendor_only and not po and not hits and CARRIER.search(str(e.get("vendor") or "")) and not (v and v.get("name") and CARRIER.search(v["name"]) is None):
        return None, "info: Dienstleister (%s) ohne Bestellbezug (Paket/Zoll/Spedition)" % e.get("vendor")
    if vendor_only and not po and e.get("type") not in ORDER_TYPES:   # Muster/Artwork/Allgemeines ohne Bestellung: Info, auch wenn ein Style genannt ist (z. B. Fitting-Kommentare)
        return None, "info: kein PO-Bezug (%s ohne Bestellung, z. B. Muster/Artwork/Allgemeines)" % e.get("type")
    if vendor_only and not po and not ref.get("style"):
        if v:
            mine = [o for o in orders if (o.get("manufacturer") or {}).get("id") == v["id"] and _status(o) not in ACTIVE_NOT]
            if len(mine) == 1:
                return mine[0], "vendor_only"
            if len(mine) > 1:
                words = " ".join([str(e.get("summary") or ""), str(e.get("source_quote") or "")]).lower()
                named = [o for o in mine if any(re.search(r"\b%s\b" % re.escape(w), words) for w in title_words(o, v["name"]))]
                if len(named) == 1:   # Text nennt ein unterscheidendes Wort aus genau EINEM Order-Titel (z. B. Projektname)
                    return named[0], "vendor_title"
                return None, "mehrdeutig: %d laufende Orders von %s" % (len(mine), v["name"])
    return None, "keine Order gefunden"


def _status(o):
    s = o.get("status")
    return s.get("status") if isinstance(s, dict) else s


def milestone(e):
    m = str((e.get("details") or {}).get("milestone") or "").upper().strip()
    if m.startswith("INSPECTION"): m = "INSPECTION"
    return m


def status_objects(orders):
    """Statusobjekte (id/status/color/order) aus den vorhandenen Orders: das PLM kennt sie nur dort."""
    out = {}
    for o in orders:
        st = o.get("status")
        if isinstance(st, dict) and st.get("status") and st.get("id"):
            out[st["status"]] = {k: st.get(k) for k in ("id", "status", "color", "order")}
    return out


WEAK = {"vendor_only": " [Zuordnung: einzige laufende Order des Lieferanten, nicht per PO-Nr belegt]",
        "vendor_title": " [Zuordnung: Lieferant + Projektname im Text, nicht per PO-Nr belegt]",
        "thread": " [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]"}


def plan(events, orders, vendors, aliases=None, vendor_aliases=None, vendor_only=False, products=None):
    per = {}
    unmatched = []
    seen = set()
    idx = order_index(orders, products) if products is not None else None
    evs = []
    for e in sorted(events, key=lambda x: str(x["_mail"].get("date") or "")):
        mk = marker(e)
        if mk in seen:
            continue
        seen.add(mk)
        evs.append(e)
    results = [(e, find_order(e, orders, vendors, aliases, vendor_aliases, vendor_only, idx)) for e in evs]
    if vendor_only:   # Verlaufs-Zuordnung: Ereignisse ohne eigenen Bezug erben die Order, auf die BELEGTE Ereignisse desselben Mail-Verlaufs eindeutig zeigen (nur Notiz, nie Termin/Status/Zahlung)
        by_thread = {}
        for e, (o, why) in results:
            tk = thread_key(e)
            if o and why not in WEAK and tk:
                by_thread.setdefault(tk, {})[o["id"]] = o
        fixed = []
        for e, (o, why) in results:
            tk = thread_key(e)
            cand = next(iter(by_thread[tk].values())) if tk and len(by_thread.get(tk, {})) == 1 else None
            # eine Mehrdeutigkeit zwischen konkreten Orders darf der Verlauf nur aufloesen, wenn seine Order darunter ist
            consistent = cand is not None and (why == "keine Order gefunden" or cand["title"] in why or (why.startswith("mehrdeutig:") and "laufende Orders" in why))
            if not o and not why.startswith("info:") and cand is not None and e.get("type") in ORDER_TYPES and consistent:
                fixed.append((e, (cand, "thread")))
            else:
                fixed.append((e, (o, why)))
        results = fixed
    for e, (o, why) in results:
        mk = marker(e)
        if not o:
            unmatched.append({"event": e, "reason": why})
            continue
        p = per.setdefault(o["id"], {"id": o["id"], "title": o["title"], "orderNumber": o.get("orderNumber"), "lines": [], "date_patch": {}, "date_mail": "", "pay": []})
        weak = why in WEAK   # nur ueber den Lieferanten/Verlauf zugeordnet: Notizzeile ja, Termin-/Zahlungs-/Statusaenderung nein
        txt = line(e) + WEAK.get(why, "")
        p["lines"].append({"marker": mk, "text": txt, "type": e.get("type"), "mail_date": str(e["_mail"].get("date") or ""), "weak": weak})
        d = e.get("details") or {}
        if weak:
            continue
        ms_ = milestone(e)
        if e.get("type") == "SHIPMENT" or ms_ in ("SHIPPED", "DELIVERED", "ARRIVED_WAREHOUSE"):
            dd = e.get("details") or {}
            p.setdefault("ship", []).append({"marker": mk, "milestone": ms_, "mode": str(dd.get("mode") or ""), "text": str(e.get("summary") or ""),
                                              "tracking": str(dd.get("tracking") or dd.get("tracking_number") or dd.get("awb") or "")})
        tgt = MILESTONE_TARGET.get(milestone(e))
        if tgt and (e.get("confidence") or 0) >= MIN_CONF_STATUS and e.get("type") != "SAMPLE":
            sobj = status_objects(orders).get(tgt)
            cur = o.get("status") if isinstance(o.get("status"), dict) else {}
            curn = STATUS_ORDER.get(cur.get("status"), cur.get("order") or 0)
            if sobj and STATUS_ORDER[tgt] > curn and cur.get("status") != "Complete":
                best = p.get("status")
                if not best or STATUS_ORDER[tgt] > STATUS_ORDER[best["to"]["status"]]:
                    p["status"] = {"to": sobj, "from": cur.get("status"), "why": "%s (%s)" % (milestone(e), str(e["_mail"].get("id")))}
        if e.get("type") == "SCHEDULE" and (e.get("confidence") or 0) >= MIN_CONF_DATE:
            md = str(e["_mail"].get("date") or "")
            for src, dst in (("new_ex_factory", "exFactoryExpectedDate"), ("new_etd", "etdEstimatedDate")):
                dd = core.parse_date(d.get(src))
                if dd:   # Ereignisse sind nach Mail-Datum sortiert: spaetere ueberschreiben fruehere
                    p["date_patch"][dst] = core.iso(dd)
                    p["date_mail"] = md
        if e.get("type") == "PAYMENT" and d.get("paid") is True and d.get("amount") not in (None, ""):
            try:
                p["pay"].append({"amount": core.r2(d["amount"]), "marker": mk})
            except (TypeError, ValueError):
                pass
    return {"orders": list(per.values()), "unmatched": unmatched}


def make_js(plan_):
    tpl = (Path(__file__).parent / "events_template.js").read_text()
    return tpl.replace("__PLAN__", json.dumps(plan_["orders"], ensure_ascii=False, separators=(",", ":")))


def report(plan_):
    lines = ["# Ereignisse -> PLM", ""]
    for p in plan_["orders"]:
        lines.append("## #%s %s" % (p["orderNumber"], p["title"]))
        lines += ["- " + l["text"] for l in p["lines"]]
        if p["date_patch"]:
            lines.append("- DATUM: %s" % p["date_patch"])
        if p.get("status"):
            lines.append("- STATUS: %s -> %s (Meilenstein %s)" % (p["status"]["from"], p["status"]["to"]["status"], p["status"]["why"]))
        for z in p["pay"]:
            lines.append("- ZAHLUNG bezahlt: %.2f" % z["amount"])
    info = [u for u in plan_["unmatched"] if str(u["reason"]).startswith("info:")]
    human = [u for u in plan_["unmatched"] if not str(u["reason"]).startswith("info:")]
    if human:
        lines += ["", "## Nicht zugeordnet (Mensch schaut)"]
        for u in human:
            e = u["event"]
            lines.append("- [%s] %s: %s (%s) -> %s" % (e["_mail"].get("date"), e.get("type"), e.get("summary"), (e.get("ref") or {}).get("po_number") or e.get("vendor"), u["reason"]))
    if info:
        lines += ["", "## Info ohne PO-Bezug (Muster/Artwork/Allgemeines): bleibt im Blatt 'Ereignisse', kein Handlungsbedarf im PLM", "- %d Ereignisse" % len(info)]
    return "\n".join(lines) + "\n"
