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
            e["_mail"] = {"id": d.get("mail_id"), "date": d.get("mail_date"), "from": d.get("from"), "subject": d.get("subject"), "thread": d.get("thread_id")}
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
    pname = {p["id"]: " ".join(str(p.get(k) or "") for k in ("name", "description")) for p in products or []}
    idx = {}
    for o in orders:
        skus = {sku[i["product"]["id"]] for i in o.get("items") or [] if isinstance(i.get("product"), dict) and i["product"].get("id") in sku}
        pw = set()
        for i in o.get("items") or []:
            if isinstance(i.get("product"), dict):
                pw |= set(re.findall(r"[a-z]{4,}", pname.get(i["product"].get("id"), "").lower()))
        idx[o["id"]] = {"skus": skus, "idents": id_tokens(o.get("_notes")) | id_tokens(o.get("poNumber")), "pwords": pw}
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
    try:   # gelernte Absender-Domains (plm_intake.vendor_domains): nur benutzbare (>= 2 Mails, kein Konflikt)
        from plm_intake import vendor_domains
        for d, ids in vendor_domains.usable(vendor_domains.load(Path(__file__).resolve().parents[1] / "output" / "intake" / "vendor_domains.json")).items():
            m.setdefault(d, set()).update(ids)
    except Exception:
        pass
    return m


CODE_LIKE_VENDOR = re.compile(r"(?=(?:\D*\d){4})[A-Za-z]{0,6}[-_]?\d[\d_\-./]*[A-Za-z0-9]{0,3}")


def vendor_plausible(name):
    """False, wenn der 'Lieferant' des Ereignisses wie Style/SKU/Rechnungsnummer aussieht (561874_2510, SNM26-005, TE-26-2003-A): ein Firmenname hat Woerter."""
    s = str(name or "").strip()
    return bool(s) and not CODE_LIKE_VENDOR.fullmatch(s)


def vendor_of(e, vendors, vendor_aliases=None, dom=None):
    """Lieferant aus dem Ereignis (tuerkische Sonderzeichen tolerant), sonst aus der Absender-Domain der Mail (nicht smilodox)."""
    if e.get("vendor") and vendor_plausible(e["vendor"]):
        v, _ = core.match_vendor(str(e["vendor"]).translate(TR), vendors, vendor_aliases)
        if v:
            return v
    m = re.search(r"@([\w.-]+)", str((e.get("_mail") or {}).get("from") or ""))
    d = m.group(1).lower() if m else ""
    ids = (dom or {}).get(d) or set()
    if d and "smilodox" not in d and len(ids) == 1:
        vid = next(iter(ids))
        return next((v for v in vendors if v["id"] == vid), None)
    # schwaches Zusatzsignal (nur Lieferantenwahl, nie Order-Zuordnung): genau EIN Lieferanten-Kuerzel (z. B. ALP) als eigenes Token in Betreff/Zusammenfassung/PO-Nr
    try:
        from plm_intake import vendor_ids
        idm = vendor_ids.load_id_map()
        txt = " ".join(str(x or "") for x in (e.get("po_number"), (e.get("ref") or {}).get("po_number"), e.get("subject"), (e.get("_mail") or {}).get("subject")))
        hit = vendor_ids.vendor_hint(txt, vendors, idm)
        if len(hit) == 1:
            return next((v for v in vendors if v["id"] == next(iter(hit))), None)
    except Exception:
        pass
    vid = e.get("_vendor_inferred")   # aus dem Mail-Verlauf / zitierten Absendern abgeleitet (infer_vendors), nie aus Smilodox-Absendern
    return next((v for v in vendors if v["id"] == vid), None) if vid else None


FREE_MAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "yahoo.com", "qq.com", "163.com", "126.com", "icloud.com", "web.de", "gmx.de", "gmx.net", "live.com", "foxmail.com"}


def forward_vendor(body, vendors, dom):
    """Lieferant aus dem zitierten Mailverlauf einer weitergeleiteten Mail: Absender-/Empfaenger-Domains im Text (From:/Von:/To:/Nachricht von ...),
    ohne Smilodox und ohne Freemail. Genau EIN Lieferant ueber alle Domains = Treffer, sonst None."""
    ids = set()
    for d in re.findall(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)", str(body or "")):
        d = d.lower()
        if "smilodox" in d or d in FREE_MAIL:
            continue
        ids |= (dom or {}).get(d) or set()
    return next((v for v in vendors if v["id"] == next(iter(ids))), None) if len(ids) == 1 else None


def _vkey(e):
    """Betreff-Schluessel fuer die Lieferanten-Ableitung (kuerzer erlaubt als thread_key: 'label list' ist weitergeleitet oft der einzige Anker; Eindeutigkeit prueft infer_vendors)."""
    sub = re.sub(r"^(\s*(re|fwd?|aw|wg|tr)\s*:\s*)+", "", str((e.get("_mail") or {}).get("subject") or ""), flags=re.I)
    k = re.sub(r"[^a-z0-9]", "", sub.lower())
    return k if len(k) >= 8 else None


def infer_vendors(evs, vendors, vendor_aliases=None, dom=None):
    """Ereignisse ohne erkannten Lieferanten (v. a. weitergeleitete 'Fwd:'/'WG:'-Mails von Smilodox-Kollegen) bekommen den Lieferanten ihres Verlaufs:
    1) zitierter Mailtext (nur wenn e['_mail']['body'] vorhanden, offline), 2) Ereignisse DERSELBEN Mail oder desselben Betreff-Verlaufs (thread_key) mit erkanntem Lieferanten,
    aber nur wenn dort genau EIN Lieferant vorkommt. Setzt e['_vendor_inferred'] (Vendor-ID); aendert sonst nichts."""
    by = {}
    for e in evs:
        v = vendor_of(e, vendors, vendor_aliases, dom)
        if v:
            for k in (("m", (e.get("_mail") or {}).get("id")), ("t", _vkey(e))):
                if k[1]:
                    by.setdefault(k, set()).add(v["id"])
    n = 0
    for e in evs:
        if vendor_of(e, vendors, vendor_aliases, dom):
            continue
        v = forward_vendor((e.get("_mail") or {}).get("body"), vendors, dom)
        vid = v["id"] if v else None
        if not vid:
            for k in (("m", (e.get("_mail") or {}).get("id")), ("t", _vkey(e))):
                if k[1] and len(by.get(k, ())) == 1:
                    vid = next(iter(by[k])); break
        if vid:
            e["_vendor_inferred"] = vid; n += 1
    return n


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


_APPROX = re.compile(r"(approx\w*\.?|ca\.?|circa|about|around|roughly|etwa|rund|up to|bis zu|~)\s*$", re.I)
_RANGE_BEFORE = re.compile(r"\d\s*(?:-|\u2013|\u2014|to|bis)\s*$", re.I)
_RANGE_AFTER = re.compile(r"^\s*(?:k\b)?\s*(?:-|\u2013|\u2014|to\b|bis\b)\s*\d", re.I)


def exact_pieces(e):
    """Genau EINE exakte Stueckzahl oder None. Keine Spannen (5000-6000), keine Naeherungen (approx./ca./~/about), keine zwei verschiedenen Zahlen.
    Nur diese Zahl darf eine Order per Menge zuordnen (schwache Regel: im Zweifel offen lassen)."""
    txt = " ".join([str(e.get("summary") or ""), str(e.get("source_quote") or "")])
    nums = set()
    d = e.get("details") or {}
    for k in ("qty", "quantity", "pieces", "total_pieces"):
        try:
            if d.get(k) not in (None, "", False) and float(d[k]) >= 500:
                nums.add(int(float(d[k])))
        except (TypeError, ValueError):
            pass
    for m in re.finditer(r"\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{4,6}\b|\b\d{1,3}\s?k\b", txt, flags=re.I):
        t = m.group(0)
        if t[-1] in "kK":
            val = int(re.sub(r"\D", "", t)) * 1000
        else:
            val = int(re.sub(r"[.,]", "", t))
        if val < 500:
            continue
        before, after = txt[max(0, m.start() - 14):m.start()], txt[m.end():m.end() + 14]
        if re.search(r"\d[./\-]$", before) or re.match(r"[./\-]\d", after):   # Teil eines Datums (20.10.2026), keine Stueckzahl
            continue
        if _APPROX.search(before) or _RANGE_BEFORE.search(before) or _RANGE_AFTER.search(after):
            return None
        nums.add(val)
    return next(iter(nums)) if len(nums) == 1 else None


def _by_exact_qty(e, cands):
    """Kandidaten, deren Gesamtmenge (+-1,5 %) zur einen exakten Zahl passt; nur laufende Orders (nicht Complete)."""
    n = exact_pieces(e)
    if not n:
        return []
    return [o for o in cands if _status(o) not in ACTIVE_NOT and abs(n - float(o.get("totalNumberOfPieces") or 0)) <= 0.015 * n]


def _ev_styles(e):
    ref = e.get("ref") or {}
    out = set()
    for part in re.split(r"[,;/\s]+", str(ref.get("style") or "")):
        n = core.norm(part)
        if len(n) >= 4 and re.search(r"\d", n):
            out.add(n)
    return out


def _deviates(e, o, idx=None):
    """Schwache Zuordnung (ohne PO-Nr): weichen Menge UND Styles des Ereignisses klar von der Order ab (core.clear_mismatch)? -> Text oder None.
    Menge = EINE exakte Zahl im Ereignis (exact_pieces); Styles = ref.style des Ereignisses gegen SKUs/Positionsnamen der Order."""
    n = exact_pieces(e)
    if not n:
        return None
    theirs = set(idx.get(o["id"], {}).get("skus", ())) if idx else set()
    theirs |= {core.norm(i.get("name")) for i in o.get("items") or []} - {""}
    off, why = core.clear_mismatch(n, o.get("totalNumberOfPieces"), _ev_styles(e), theirs)
    return "%s: %s" % (o.get("title"), why) if off else None


GENERAL_TYPES = ("SAMPLE", "OTHER", "ORDER_CHANGE", "DELAY")
GENERAL_TOPIC = re.compile(r"\b(labels?|etikett\w*|hang ?tags?|care label|barcodes?|stickers?|layout|carton marking|packaging|artwork|streik\w*|strike|development|entwicklung\w*|patterns?|logo)\b", re.I)
BELEG_WORT = re.compile(r"zahlung|payment|invoice|rechnung|proforma|b/l|bill of lading|\\bhbl\\b|\\bawb\\b|container|vessel|shipped|verschifft|\\bprice\\b|preis|\\bpaid\\b|bezahlt", re.I)   # Beleg-/Zahlungs-/Versandsprache: nie allgemein
_DATE = re.compile(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b")


def _general_topic(e):
    """Allgemeines Thema ohne Bestellbezug (Etiketten, Barcode-Layout, Streik, Entwicklungsprogramm): Typ SAMPLE/OTHER/ORDER_CHANGE/DELAY, Thema im Betreff/Text UND
    keinerlei Kennung (PO/Style/Container/Rechnung/Nummern >= 3 Ziffern), Menge oder Betrag. Nur zusammen mit 'kein Lieferant erkannt' benutzt (find_order)."""
    if e.get("type") not in GENERAL_TYPES:
        return False
    ref = e.get("ref") or {}
    d = e.get("details") or {}
    if any(ref.get(k) for k in ("po_number", "style", "container")) or event_tokens(e) or text_codes(e) or mentioned_pieces(e):
        return False
    if any(d.get(k) not in (None, "", False) for k in ("qty", "quantity", "pieces", "amount", "total", "invoice_number") + tuple(IDENT_KEYS)):
        return False
    txt = " ".join([str(e.get("summary") or ""), str(e.get("source_quote") or "")])
    if re.search(r"\d{3,}|[$\u20ac]|\b(usd|eur)\b", _DATE.sub(" ", txt), re.I):
        return False
    subj = str((e.get("_mail") or {}).get("subject") or "")
    return bool(GENERAL_TOPIC.search(txt + " " + subj)) and not BELEG_WORT.search(txt + " " + subj)


def _general_info(e, why, vendors, vendor_aliases, dom):
    """Info-Grund (str) fuer ein allgemeines Thema ohne Bestellbezug, sonst None. Erst NACH der Verlaufs-Zuordnung (plan), damit Ereignisse belegter Verlaeufe ihre Order erben.
    Faelle: (a) kein Lieferant erkannt und keine Order gefunden; (b) Lieferant nur aus dem Verlauf abgeleitet (kein eigener Beleg) und nur 'mehrdeutig: N laufende Orders' (ohne Order-Namen)."""
    if not _general_topic(e):
        return None
    v = vendor_of(e, vendors, vendor_aliases, dom)
    if why == "keine Order gefunden" and not v:
        return "info: allgemeines Thema ohne Lieferant/Bestellbezug (%s)" % e.get("type")
    if v and e.get("_vendor_inferred") and str(why).startswith("mehrdeutig:") and "laufende Orders" in str(why):
        return "info: allgemeines Thema ohne Bestellbezug (%s, Lieferant nur aus Verlauf: %s)" % (e.get("type"), v["name"])
    return None


SAMPLE_WORT = re.compile(r"\bsamples?\b|\bmuster\w*|photo ?samples?|pre-?production|\bpps\b|\bsms\b", re.I)
SAMPLE_NOT = re.compile(r"invoice|rechnung|proforma|b/l|bill of lading|container|payment|zahlung|\bpaid\b|\bprice[sd]?\b|preis|quot\w+|bulk|mass production|[$\u20ac]|\b(usd|eur)\b", re.I)
SAMPLE_QTY = re.compile(r"(\d[\d.,]*)\s*(?:pcs|pieces|stk|st\u00fcck|units|cartons?|pairs)\b", re.I)
SAMPLE_MAX_QTY = 50   # bis hierher sind Stueckzahlen Musterstuecke, keine Bestellmengen


def _sample_info(e, why):
    """Info-Grund (str) fuer Musterereignisse ohne Order-/Beleg-Kennung (Musterfotos, Musterversand, Musterstatus), sonst None. Greift nur, wenn die Order-Suche scheiterte
    (mehrdeutig / abweichend / keine Order). Nie bei PO-Nr, Container, Beleg-Feldern (Rechnung/B/L), Betraegen, Preisen/Angeboten, Serienproduktion oder Stueckzahlen > 50.
    Typ SAMPLE; Typ SHIPMENT nur, wenn der Text Muster nennt. Sendungsnummern (tracking/awb) eines Musterpakets sind keine Order-Kennung."""
    if e.get("type") not in ("SAMPLE", "SHIPMENT") or not (str(why).startswith(("mehrdeutig:", "abweichend:")) or why == "keine Order gefunden"):
        return None
    ref = e.get("ref") or {}
    d = e.get("details") or {}
    if any(ref.get(k) for k in ("po_number", "container")):
        return None
    if any(d.get(k) not in (None, "", False) for k in ("amount", "total", "total_cost", "prices", "price", "invoice_number", "invoice_no", "invoice", "po_number", "po", "order", "container", "bl", "hbl", "mbl")):
        return None
    for k in ("qty", "quantity", "pieces", "sample_qty"):
        try:
            if d.get(k) not in (None, "", False) and float(d[k]) > SAMPLE_MAX_QTY:
                return None
        except (TypeError, ValueError):
            return None
    txt = " ".join([str(e.get("summary") or ""), str(e.get("source_quote") or "")])
    from plm_intake import po_ids
    if po_ids.find_po_ids(txt) or SAMPLE_NOT.search(_DATE.sub(" ", txt)):
        return None
    for m in SAMPLE_QTY.finditer(txt):
        try:
            if float(m.group(1).replace(",", "")) > SAMPLE_MAX_QTY:
                return None
        except ValueError:
            return None
    if e.get("type") == "SHIPMENT" and not SAMPLE_WORT.search(txt):
        return None
    return "info: Muster ohne Order-/Beleg-Kennung (%s)" % e.get("type")


def _content(e, cands, idx, vendor_only, v=None):
    """Inhaltsbasierte Zuordnung (plm_intake.content_match) NUR im Mehrdeutigkeitsfall, nur mit Schalter CONTENT_MATCH=1, nur bei bekanntem Lieferanten (v) und nur unter
    dessen laufenden Orders (vendor_only-Lauf). -> (Order, 'inhalt') oder None."""
    from plm_intake import content_match
    if not (vendor_only and v and content_match.enabled()):
        return None
    cands = [o for o in cands if (o.get("manufacturer") or {}).get("id") == v["id"]]
    if len(cands) < 2:
        return None
    o, beleg, _det = content_match.match(e, cands, idx)
    if not o:
        return None
    e["_content_hit"] = beleg
    return o, "inhalt"


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
    by_po = bool(hits)
    if not hits:   # Style: auch eine 'PO-Nr', die in Wahrheit eine Stylenummer ist (26M10_001, AL29008), und Listen 'GT0301, GT0302'
        sts = codes(ref.get("style"), ref.get("po_number")) + [x for x in [core.norm(ref.get("style"))] if len(x) >= 4]   # auch beschreibende Styles ('fleece kenna jacket')
        for o in orders:
            names = [core.norm(i.get("name")) for i in o.get("items") or []]
            skus = idx.get(o["id"], {}).get("skus", ()) if idx else ()
            if any(any(st in n for n in names) or any(k == st or k.startswith(st) for k in skus) for st in sts):
                hits.append(o)
    from_style = bool(hits) and not by_po
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
        q = _by_exact_qty(e, hits)
        if len(q) == 1:
            hits, by_qty = q, True
    if hits and (from_style or via_text):   # schwacher Weg (nur Style/Text, kein PO-Nr-/Kennungs-Treffer): Menge UND Styles gegenpruefen
        bad = {o["id"]: m for o in hits for m in [_deviates(e, o, idx)] if m}
        hits = [o for o in hits if o["id"] not in bad]
        if bad and not hits:
            return None, "abweichend: Menge und Styles passen nicht zur Order (%s)" % "; ".join(bad.values())[:200]
    if len(hits) == 1:
        subj_ref = str((e.get("details") or {}).get("ref_quelle") or "") == "betreff"   # Style nur aus Betreff/Anhangsnamen abgeleitet (Apps Script-Rueckfall): nur Notiz
        return hits[0], ("menge" if by_qty else "text" if (via_text or subj_ref) else "ok")
    if hits:
        got = _content(e, [o for o in hits if _status(o) not in ACTIVE_NOT], idx, vendor_only, v)
        if got:
            return got
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
                q = _by_exact_qty(e, mine)   # EINE exakte Zahl (keine Spanne/Naeherung) passt (+-1,5 %) zu genau EINER laufenden Order des Lieferanten
                if len(q) == 1:
                    return q[0], "menge"
                words = " ".join([str(e.get("summary") or ""), str(e.get("source_quote") or "")]).lower()
                named = [o for o in mine if any(re.search(r"\b%s\b" % re.escape(w), words) for w in title_words(o, v["name"]))]
                if len(named) == 1:   # Text nennt ein unterscheidendes Wort aus genau EINEM Order-Titel (z. B. Projektname)
                    return named[0], "vendor_title"
                got = _content(e, mine, idx, vendor_only, v)
                if got:
                    return got
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
        "verlauf": " [Zuordnung: ueber Mail-Verlauf zugeordnet (alle zugeordneten Ereignisse des Gmail-Verlaufs gehoeren zu dieser Order), nicht per PO-Nr belegt]",
        "text": " [Zuordnung: Stylecode im Ereignistext, nicht per PO-Nr belegt]",
        "menge": " [Zuordnung: genannte Stueckzahl passt zu genau einer Order, nicht per PO-Nr belegt]",
        "inhalt": " [Zuordnung: inhaltlich zugeordnet, nicht per PO-Nr belegt]"}


INFO_OVERRIDE = "__info__"


def load_event_overrides(intake):
    """output/intake/event_overrides.json {"<ev-marker 8 hex>": "<order_id>" | "__info__"} (Entscheidungen aus der Klaerung)."""
    f = Path(intake) / "event_overrides.json"
    try:
        d = json.load(open(f)) if f.exists() else {}
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def load_thread_orders(intake):
    """output/intake/mail_threads.json {Thread-ID: [Order-ID, ...]} (gelernt, plm_intake.mail_threads)."""
    from plm_intake import mail_threads
    return mail_threads.load(Path(intake) / "mail_threads.json")


def _by_mail_thread(results, assigned, by_oid, thread_orders, vendors, vendor_aliases, dom):
    """Mail-Verlauf (Gmail-Thread, plm_intake.mail_threads): ein Ereignis ohne Order erbt die Order, auf die ALLE sicher zugeordneten Ereignisse seines Verlaufs zeigen
    (genau EINE Order; gespeicherter Stand + dieser Lauf), nur wenn sein Lieferant (falls erkannt) zur Order passt. Mehrere Orders im Verlauf = nicht zuordnen. Grund 'verlauf' (schwach: nur Notiz)."""
    from plm_intake import mail_threads
    if not mail_threads.enabled():
        return results
    tmap = {t: list(v) for t, v in (thread_orders or {}).items()}
    mail_threads.learn(tmap, assigned)
    out = []
    for e, (o, why) in results:
        t = (e.get("_mail") or {}).get("thread")
        ids = set(tmap.get(t) or ()) if t else set()
        cand = by_oid.get(next(iter(ids))) if len(ids) == 1 else None
        if (o or not cand or why.startswith("info:") or why.startswith("abweichend") or _status(cand) in ACTIVE_NOT
                or not (why == "keine Order gefunden" or cand["title"] in why or (why.startswith("mehrdeutig:") and "laufende Orders" in why))):
            out.append((e, (o, why))); continue
        v = vendor_of(e, vendors, vendor_aliases, dom)
        if v and (cand.get("manufacturer") or {}).get("id") != v["id"]:
            out.append((e, (o, why))); continue
        out.append((e, (cand, "verlauf")))
    return out


def plan(events, orders, vendors, aliases=None, vendor_aliases=None, vendor_only=False, products=None, style_aliases=None, event_overrides=None, thread_orders=None):
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
    infer_vendors(evs, vendors, vendor_aliases, dom)
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
        results = _by_mail_thread(results, assigned, by_oid, thread_orders, vendors, vendor_aliases, dom)
        results = [(e, (o, why if o else (_general_info(e, why, vendors, vendor_aliases, dom) or _sample_info(e, why) or why))) for e, (o, why) in results]
    for e, (o, why) in results:
        mk = marker(e)
        if not o:
            unmatched.append({"event": e, "reason": why})
            continue
        p = per.setdefault(o["id"], {"id": o["id"], "title": o["title"], "orderNumber": o.get("orderNumber"), "lines": [], "date_patch": {}, "date_mail": "", "pay": []})
        weak = why in WEAK   # nur ueber den Lieferanten/Verlauf zugeordnet: Notizzeile ja, Termin-/Zahlungs-/Statusaenderung nein
        txt = line(e) + WEAK.get(why, "")
        if why == "inhalt" and e.get("_content_hit"):
            txt = line(e) + " [Zuordnung: inhaltlich zugeordnet: %s; nicht per PO-Nr belegt]" % str(e["_content_hit"])[:160]
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
