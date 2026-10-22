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
    """Kennungen (Container, B/L, AWB, Rechnungs-/PO-Nummern) aus Freitext: mindestens 7 Zeichen mit Buchstaben UND Ziffern. Mail-IDs und Marker-Hashes zaehlen nicht."""
    out = set()
    for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9._/\-]{5,}", str(text or "")):
        n = core.norm(t)
        if len(n) >= 7 and re.search(r"[a-z]", n) and re.search(r"\d", n) and not re.fullmatch(r"[0-9a-f]{8}|[0-9a-f]{16}", n):
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


TEST_ORDER = re.compile(r"ZZ|(?:^|-)T1(?:-|$)", re.I)   # Testobjekte (ZZ-*, *-T1, *-KH-T1-EXTRA) nie als Ziel: sonst Scheinmehrdeutigkeit (LIEFERANT_D-T1 vs. LIEFERANT_D-ALI...)
TR = str.maketrans("İıŞşĞğÜüÖöÇç", "IiSsGgUuOoCc")
CODE = re.compile(r"[A-Za-z]{0,6}[-_ ]?\d{3,}[A-Za-z0-9_\-]*")


def codes(*vals):
    """Einzelne Kennungen aus Feldern wie 'GT0301, GT0302', '26022(GT0303)', 'Siera Pant (Style 26385)', 'XW26-008, XW26-009'."""
    out = []
    for v in vals:
        if not v:
            continue
        for part in [str(v)] + re.split(r"[,;/()\s]+", str(v)) + CODE.findall(str(v)):
            n = core.norm(part)
            if len(n) >= 4 and re.search(r"\d", n) and n not in out:
                out.append(n)
    return out


def domain_vendors(vendors):
    """Mail-Domain -> Vendor-IDs (Kontakte im PLM + output/phase2/lieferanten.json)."""
    m = {}
    for v in vendors:
        for c in v.get("contacts") or []:
            if "@" in str(c.get("email") or ""):
                m.setdefault(c["email"].split("@")[-1].lower(), set()).add(v["id"])
    try:
        cfg = json.load(open(Path(__file__).resolve().parents[1] / "output" / "phase2" / "lieferanten.json"))
        byname = {core.norm(v["name"]): v["id"] for v in vendors}
        for c in cfg["lieferanten"].values():
            vid = byname.get(core.norm(c["vendor"]))
            for d in c.get("domain") or []:
                if vid:
                    m.setdefault(d.lower(), set()).add(vid)
    except Exception:
        pass
    return m


def vendor_of(e, vendors, vendor_aliases=None, dom=None):
    """Lieferant aus dem Ereignis (tuerkische Sonderzeichen tolerant), sonst aus der Absender-Domain der Mail (nicht smilodox)."""
    if e.get("vendor"):
        v, _ = core.match_vendor(str(e["vendor"]).translate(TR), vendors, vendor_aliases)
        if v:
            return v
    m = re.search(r"@([\w.-]+)", str((e.get("_mail") or {}).get("from") or ""))
    d = m.group(1).lower() if m else ""
    ids = (dom or {}).get(d) or set()
    if d and "smilodox" not in d and len(ids) == 1:
        vid = next(iter(ids))
        return next((v for v in vendors if v["id"] == vid), None)
    return None


STYLE_TOKEN = re.compile(r"[A-Za-z]{1,6}[-_ ]?\d{2,}[A-Za-z0-9_\-]*")


def style_alias_map(style_aliases):
    """Artikel-Aliase (HD189 = SNM26-006) in beide Richtungen: norm -> {norm, ...}."""
    m = {}
    for a, b in (style_aliases or {}).items():
        na, nb = core.norm(a), core.norm(b)
        if na and nb and na != nb:
            m.setdefault(na, set()).add(nb); m.setdefault(nb, set()).add(na)
    return m


def text_codes(e, alias_map=None):
    """Style-/Artikelcodes aus dem Ereignistext (Zusammenfassung, Zitat, Details) inkl. Alias-Varianten; nur Codes mit Buchstaben und Ziffern, mind. 5 Zeichen."""
    d = e.get("details") or {}
    txt = " ".join([str(e.get("summary") or ""), str(e.get("source_quote") or "")] + [str(v) for v in d.values() if isinstance(v, (str, int))])
    out = set()
    for t in STYLE_TOKEN.findall(txt):
        n = core.norm(t)
        if len(n) >= 5 and re.search(r"[a-z]", n) and re.search(r"\d", n):
            out.add(n)
            out |= (alias_map or {}).get(n, set())
    return out


def mentioned_pieces(e):
    """Stueckzahlen im Text: '10,000', '85.290', '32-33k', 'ca. 4500 pcs'."""
    txt = " ".join([str(e.get("summary") or ""), str(e.get("source_quote") or "")])
    nums = set()
    d = e.get("details") or {}
    for k in ("qty", "quantity", "pieces", "total_pieces"):   # Auslese liefert die Stueckzahl seit dem Referenz-Prompt als Zahl in details.qty
        try:
            if d.get(k) not in (None, "", False) and float(d[k]) >= 500:
                nums.add(int(float(d[k])))
        except (TypeError, ValueError):
            pass
    for m in re.findall(r"\b\d{1,3}(?:[.,]\d{3})+\b", txt):
        nums.add(int(re.sub(r"[.,]", "", m)))
    for m in re.findall(r"\b\d{4,6}\b", txt):
        nums.add(int(m))
    for a, b in re.findall(r"\b(\d{1,3})(?:-(\d{1,3}))?\s?k\b", txt, flags=re.I):
        nums.add(int(a) * 1000)
        if b:
            nums.add(int(b) * 1000)
    return {n for n in nums if n >= 500}


def find_order(e, orders, vendors, aliases=None, vendor_aliases=None, vendor_only=False, idx=None, dom=None, style_aliases=None):
    """Genau eine Order oder None (+ Grund). Zaehlt: PO-Nummer/Titel, Style (Positionsname oder Produkt-SKU), bekannte Kennung (Container/HBL/Rechnungsnr. aus den Notizen).
    Lieferant allein reicht nur schwach und nur bei vendor_only (mehrdeutig sonst)."""
    ref = e.get("ref") or {}
    po = core.norm(ref.get("po_number"))
    hits = []
    # Alias-Tabelle (von Menschen gepflegt oder gelernt, plm_intake/alias_learn): Lieferanten-Nummer -> Order (Titel oder ID), z. B. "ISPOB3.429": "PO-LIEFERANT_W-2026-04-29"
    # Vorrang vor allen schwaecheren Wegen. Ausser PO-Nr zaehlen auch Rechnungs-/BL-/Container-Nr des Ereignisses (exakt). Alias 'mehrdeutig' wird nie benutzt.
    d_ = e.get("details") or {}
    from plm_intake import po_ids   # Smilodox PO-ID (PO26-036) in Mail/Ereignis/Beleg = staerkstes Signal, vor Aliasen
    src0 = e.get("source")
    hit = po_ids.order_for_text(orders, ref.get("po_number"), e.get("po_number"), src0.get("doc") if isinstance(src0, dict) else src0, e.get("subject"), e.get("summary"), d_.get("subject"), (e.get("_mail") or {}).get("subject"))
    if hit:
        return hit, "po_id"
    keys = [(po, True)] if po else []
    keys += [(core.norm(x), False) for x in [ref.get("container")] + [d_.get(k) for k in ("invoice_number", "bl", "awb", "hbl", "mbl", "container")] if x not in (None, "", False) and len(core.norm(x)) >= 5]
    src = e.get("source")
    if isinstance(src, dict) and src.get("doc") and len(core.norm(src["doc"])) >= 5:   # Dokumentnummer (source.doc) zaehlt wie eine Beleg-Nr (nur exakt)
        keys.append((core.norm(src["doc"]), False))
    for alias, title in (aliases or {}).items():
        na = core.norm(alias)
        if title == "__mehrdeutig__" or not na:
            continue
        # exakt, oder die Beleg-/Positionsnummer beginnt mit dem Alias und geht nur mit Suffix weiter ('ISPOB3.429-5' zu 'ISPOB3.429'; Mindestlaenge 6 gegen Zufallstreffer)
        if any(na == k or (is_po and len(na) >= 6 and k.startswith(na)) for k, is_po in keys):
            hits = [o for o in orders if o.get("id") == title or core.norm(o.get("title")) == core.norm(title)]
            if len(hits) == 1:
                return hits[0], "alias"
            hits = []
    pos = codes(ref.get("po_number")) + ([po] if po and len(po) >= 4 else [])
    if pos:
        raw = [str(ref.get("po_number"))] + re.split(r"[,;/()\s]+", str(ref.get("po_number")))
        for o in orders:
            if any(c == core.norm(o.get("poNumber")) for c in pos) or any(core.po_in_title(r, o.get("title")) for r in raw if len(core.norm(r)) >= 4):   # Wortgrenze: '...-2' trifft nicht '...-2EXTRA'
                hits.append(o)
    if not hits:   # Style: auch eine 'PO-Nr', die in Wahrheit eine Stylenummer ist (26M10_001, AL29008), und Listen 'GT0301, GT0302'
        sts = codes(ref.get("style"), ref.get("po_number")) + [x for x in [core.norm(ref.get("style"))] if len(x) >= 4]   # auch beschreibende Styles ('fleece kenna jacket')
        for o in orders:
            names = [core.norm(i.get("name")) for i in o.get("items") or []]
            skus = idx.get(o["id"], {}).get("skus", ()) if idx else ()
            if any(any(st in n for n in names) or any(k == st or k.startswith(st) for k in skus) for st in sts):
                hits.append(o)
    if not hits and idx:   # bekannte Kennung (z. B. HBL/Container aus frueheren Notizen derselben Order)
        toks = event_tokens(e)
        if toks:
            hits = [o for o in orders if toks & idx.get(o["id"], {}).get("idents", set())]
    via_text = False
    if not hits and idx:   # Stylecodes im Ereignistext (auch Artikel-Aliase wie HD189 = SNM26-006): gegen Produkt-SKUs und Positionsnamen der Orders
        amap = style_alias_map(style_aliases)
        tcs = text_codes(e, amap)
        if tcs:
            for o in orders:
                names = [core.norm(i.get("name")) for i in o.get("items") or []]
                skus = idx.get(o["id"], {}).get("skus", ())
                if any(k in tcs for k in skus) or any(len(t) >= 6 and t in n for t in tcs for n in names):
                    hits.append(o)
            via_text = bool(hits)
    v = vendor_of(e, vendors, vendor_aliases, dom)
    if v and len(hits) > 1:   # Lieferant als Tiebreaker, wenn er die Treffer eindeutig macht
        by_v = [o for o in hits if (o.get("manufacturer") or {}).get("id") == v["id"]]
        if len(by_v) == 1:
            hits = by_v
    if len(hits) > 1:   # laufende Orders bevorzugen: abgeschlossene sind fast nie gemeint
        running = [o for o in hits if _status(o) not in ACTIVE_NOT]
        if len(running) == 1:
            hits = running
    by_qty = False
    if len(hits) > 1:   # genannte Stueckzahl passt (+-1,5 %) zu genau EINER der Kandidaten-Orders
        want = mentioned_pieces(e)
        if want:
            q = [o for o in hits if any(abs(n - float(o.get("totalNumberOfPieces") or 0)) <= 0.015 * n for n in want)]
            if len(q) == 1:
                hits, by_qty = q, True
    if len(hits) == 1:
        subj_ref = str((e.get("details") or {}).get("ref_quelle") or "") == "betreff"   # Style nur aus Betreff/Anhangsnamen abgeleitet (Apps Script-Rueckfall): nur Notiz
        return hits[0], ("menge" if by_qty else "text" if (via_text or subj_ref) else "ok")
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
                want = mentioned_pieces(e)   # genannte Stueckzahl passt (+-1,5 %) zu genau EINER laufenden Order des Lieferanten
                if want:
                    q = [o for o in mine if any(abs(n - float(o.get("totalNumberOfPieces") or 0)) <= 0.015 * n for n in want)]
                    if len(q) == 1:
                        return q[0], "menge"
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
        "thread": " [Zuordnung: gleicher Mail-Verlauf wie ein belegtes Ereignis dieser Order, nicht per PO-Nr belegt]",
        "text": " [Zuordnung: Stylecode im Ereignistext, nicht per PO-Nr belegt]",
        "menge": " [Zuordnung: genannte Stueckzahl passt zu genau einer Order, nicht per PO-Nr belegt]"}


INFO_OVERRIDE = "__info__"


def load_event_overrides(intake):
    """output/intake/event_overrides.json {"<ev-marker 8 hex>": "<order_id>" | "__info__"} (Entscheidungen aus der Klaerung)."""
    f = Path(intake) / "event_overrides.json"
    try:
        d = json.load(open(f)) if f.exists() else {}
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def plan(events, orders, vendors, aliases=None, vendor_aliases=None, vendor_only=False, products=None, style_aliases=None, event_overrides=None):
    per = {}
    invalid_overrides = []
    unmatched = []
    seen = set()
    orders = [o for o in orders if not TEST_ORDER.search(str(o.get("title") or ""))]
    idx = order_index(orders, products) if products is not None else None
    dom = domain_vendors(vendors)
    evs = []
    for e in sorted(events, key=lambda x: str(x["_mail"].get("date") or "")):
        mk = marker(e)
        if mk in seen:
            continue
        seen.add(mk)
        evs.append(e)
    by_oid = {o["id"]: o for o in orders}
    results = []
    for e in evs:
        ov = (event_overrides or {}).get(marker(e))
        if ov == INFO_OVERRIDE:   # Klaerung: ohne Bestellbezug -> still aus der Klaerliste
            results.append((e, (None, "info: Klaerung - kein Bestellbezug (Spedition/Zoll/Muster/Entwicklung/nicht im PLM)")))
            continue
        if ov:
            if ov in by_oid:   # STARKE Zuordnung (nicht in WEAK): vor allen anderen Wegen
                results.append((e, (by_oid[ov], "klaerung")))
                continue
            invalid_overrides.append({"marker": marker(e), "order_id": ov})
        results.append((e, find_order(e, orders, vendors, aliases, vendor_aliases, vendor_only, idx, dom, style_aliases)))
    assigned = [(e, o["id"], why) for e, (o, why) in results if o]   # vor der Verlaufs-Zuordnung: nur eigene Treffer (fuer plm_intake.alias_learn)
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
    return {"orders": list(per.values()), "unmatched": unmatched, "assigned": assigned, "invalid_overrides": invalid_overrides}


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
    for iv in plan_.get("invalid_overrides") or []:
        lines.append("- WARNUNG: event_overrides ev:%s -> unbekannte Order-ID %s (ignoriert)" % (iv["marker"], iv["order_id"]))
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
