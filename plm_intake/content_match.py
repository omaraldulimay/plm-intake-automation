"""Inhaltsbasierter Matcher: Ereignis -> eine von MEHREREN laufenden Orders eines bekannten Lieferanten (Mehrdeutigkeitsfall von events.find_order).

Nur Lesen und Rechnen (kein PLM-Zugriff). Je Kandidaten-Order ein Profil (Titel, Positionen/Styles/SKUs, Produktnamen, Farben, Stueckzahlen, Notizen),
je Ereignis Merkmale (Styles, Menge, unterscheidende Woerter/Programmnamen). Punkte nach Gewichten W; Zuordnung NUR wenn
  (1) der Beste mindestens MIN_SCORE hat, (2) mindestens MARGIN Punkte vor dem Zweiten liegt, (3) mindestens ein BELEGBARES Signal vorliegt
  (Style/SKU, exakte Stueckzahl, unterscheidendes Wort aus Titel/Position/Produktname, das in GENAU EINER Kandidaten-Order steht) und (4) kein klarer Widerspruch besteht.
Woerter, die in mehreren Kandidaten stehen (Lieferant, 'kunde_x' bei mehreren Kunde X-Orders), zaehlen nicht. Schwellen sind per Backtest festgelegt (plm_intake/content_backtest.py).
Die Zuordnung ist SCHWACH (events.WEAK['inhalt']): nur Notiz, nie Termin/Status/Zahlung.
"""
import os
import re

from plm_intake import core

# Schalter: Standard aus. Omar schaltet per Repo-Variable CONTENT_MATCH=1 ein (Workflow-env-Zeile).
def enabled():
    return os.environ.get("CONTENT_MATCH") == "1"


W = {"style": 6, "menge_total": 5, "menge_pos": 4, "wort": 3, "wort_notiz": 1}
WORD_CAP = 9          # hoechstens 3 unterscheidende Woerter zaehlen
MIN_SCORE = 6
MARGIN = 4
QTY_TOL = 0.015

STOP = {
    "order", "orders", "reorder", "extra", "first", "second", "third", "main", "bulk", "sample", "samples", "mail", "email", "please", "thanks", "thank", "dear",
    "regards", "hello", "kind", "best", "with", "from", "that", "this", "have", "will", "been", "were", "your", "their", "there", "which", "about", "after",
    "before", "when", "also", "need", "needs", "shipment", "shipped", "shipping", "ship", "production", "factory", "delivery", "deliver", "delivered", "payment",
    "invoice", "total", "pieces", "quantity", "price", "prices", "date", "days", "week", "weeks", "month", "confirm", "confirmed", "confirmation", "update",
    "pending", "status", "ready", "complete", "completed", "expected", "estimated", "schedule", "scheduled", "arrival", "arrive", "arrived", "vessel", "container",
    "waiting", "received", "receive", "sent", "send", "sending", "again", "still", "under", "over", "into", "other", "more", "than", "then", "them", "they",
    "some", "such", "only", "each", "both", "need", "must", "should", "would", "could", "approved", "approval", "change", "changed", "changes", "provide", "provided",
    "information", "details", "detail", "request", "requested", "regarding", "related", "follow", "following", "inspection", "quality", "issue", "issues",
    "smilodox", "product", "products", "style", "styles", "item", "items", "color", "colors", "colour", "colours", "size", "sizes", "pack", "packing", "carton", "cartons",
    "jacket", "pants", "pant", "shirt", "shirts", "hoodie", "hoodies", "black", "white", "olive", "shorts", "socks", "women", "woman", "mens", "kids", "men", "unisex",
    "leggings", "legging", "tops", "top", "tank", "bra", "bras", "sweat", "sweatshirt", "polyester", "cotton", "gsm",
    "bestellung", "lieferung", "zahlung", "rechnung", "menge", "stueck", "stuck", "versand", "ware", "datum", "bitte", "danke", "gruss", "gruesse",
}
# Programm-/Kollektionsnamen: duerfen als unterscheidendes Wort zaehlen, auch wenn sie Allerweltswoerter sind (nur wenn sie in genau EINER Order stehen)
PROGRAM_OK = {"sweat", "polyester", "kunde_y", "noos", "kunde_x", "siera", "siara", "fitness", "easy", "program", "programm", "tennis", "business", "sneaker", "crew"}

_EV_LINE = re.compile(r"^\s*\[\d{4}-\d{2}-\d{2}[^\]]*ev:[0-9a-f]{8}\][^\n]*", re.M)
_STYLE = re.compile(r"[A-Za-z]{1,6}[-_ ]?\d{2,}[A-Za-z0-9_\-]*")


def _norm_words(text):
    t = str(text or "").lower().translate(str.maketrans("äöüß", "aous"))
    return set(re.findall(r"[a-z]{4,}", t))


def _style_codes(text):
    out = set()
    for t in _STYLE.findall(str(text or "")):
        n = core.norm(t)
        if len(n) >= 5 and re.search(r"[a-z]", n) and re.search(r"\d", n):
            out.add(n)
    return out


def _qty_close(n, tot, tol=QTY_TOL):
    return bool(n and tot and abs(n - float(tot)) <= tol * n)


def profile(o, idx=None, own_mail=None):
    """Profil einer Order. idx = events.order_index (SKUs, Produktnamen-Woerter). own_mail: Mail-ID, deren Notizzeilen ausgeblendet werden (Backtest)."""
    skus = set((idx or {}).get(o["id"], {}).get("skus", ()))
    item_words, names, colors, item_qty, var_qty = set(), set(), set(), [], []
    item_words |= set((idx or {}).get(o["id"], {}).get("pwords", ()))
    for it in o.get("items") or []:
        names.add(core.norm(it.get("name")))
        item_words |= _norm_words(it.get("name"))
        q = 0
        iw = _norm_words(it.get("name")) | set((idx or {}).get(o["id"], {}).get("pwords", ()))
        for v in it.get("variants") or []:
            colors |= _norm_words(v.get("name"))
            vq = sum(float(a.get("quantity") or 0) for a in v.get("amounts") or [])
            if vq:
                var_qty.append(vq)
            q += vq
        if q:
            item_qty.append((q, iw))
    codes = set(skus) | {c for n in names for c in _style_codes(n)} | {core.norm(x) for it in o.get("items") or [] for x in [str(it.get("name") or "").split(" ")[0]] if len(core.norm(x)) >= 5 and re.search(r"\d", x)}
    notes = str(o.get("_notes") or "")
    if own_mail:
        notes = "\n".join(l for l in notes.splitlines() if str(own_mail) not in l)
    human = _EV_LINE.sub("", notes)
    title_w = _norm_words(re.sub(r"[-_]", " ", str(o.get("title") or "")))
    return {"id": o["id"], "title": o.get("title"), "total": float(o.get("totalNumberOfPieces") or 0), "item_qty": item_qty, "var_qty": var_qty, "codes": codes,
            "title_w": title_w, "item_w": item_words, "colors": colors, "note_w": _norm_words(human), "evnote_w": _norm_words(" ".join(_EV_LINE.findall(notes)))}


def _multi_subject(sub):
    """Sammel-Betreff ('KUNDE_X / Kunde Y Q2 2027 / XTRAFIT / Easy Fitness'): nennt mehrere Programme, unterscheidet also nichts."""
    t = str(sub or "")
    return t.count("/") >= 2 or t.count("|") >= 2 or t.count(",") >= 3


def event_features(e):
    """Merkmale aus Zusammenfassung, Zitat, Betreff, Details (kein Mail-Text noetig)."""
    d = e.get("details") or {}
    parts = [e.get("summary"), e.get("source_quote")] + ([] if _multi_subject((e.get("_mail") or {}).get("subject")) else [(e.get("_mail") or {}).get("subject")]) + [e.get("subject")]
    parts += [v for k, v in d.items() if isinstance(v, str) and k not in ("mode", "currency", "milestone", "status", "carrier", "vessel")]
    parts += [d.get(k) for k in ("style", "styles", "item", "color", "colors") if d.get(k)]
    parts.append((e.get("ref") or {}).get("style"))
    txt = " ".join(str(p) for p in parts if p)
    return {"text": txt, "codes": _style_codes(txt) | {core.norm(x) for x in re.split(r"[,;/\s]+", str((e.get("ref") or {}).get("style") or "")) if len(core.norm(x)) >= 4 and re.search(r"\d", x)},
            "words": _norm_words(txt) - STOP | (_norm_words(txt) & PROGRAM_OK)}


def match(e, cands, idx=None, own_mail=None, extra_codes=None, vendor_name=""):
    """-> (order | None, Beleg-Text | None, Details). Details: {'ranking': [(titel, score, [Treffer])], 'reason': ...}."""
    from plm_intake import events
    if len(cands) < 2:
        return None, None, {"reason": "weniger als 2 Kandidaten"}
    prof = [profile(o, idx, own_mail) for o in cands]
    f = event_features(e)
    vwords = _norm_words(vendor_name) | _norm_words(" ".join(str((o.get("manufacturer") or {}).get("name") or "") for o in cands[:1]))
    codes = set(f["codes"]) | set(extra_codes or ())
    qx = events.exact_pieces(e)
    res = []
    n = len(prof)
    # Haeufigkeit je Wort ueber die Kandidaten (Titel/Position/Produkt): nur Woerter in GENAU EINER Order sind unterscheidend
    df = {}
    for p in prof:
        for w in p["title_w"] | p["item_w"]:
            df[w] = df.get(w, 0) + 1
    evw = _norm_words(f["text"])
    for o, p in zip(cands, prof):
        score, hits = 0, []
        uniq_style = qty_total = qty_pos = False
        sh = sorted(c for c in codes if c in p["codes"] or any(len(c) >= 6 and c in k for k in p["codes"]))
        if sh:
            score += W["style"]; hits.append("Style %s" % sh[0].upper())
            uniq_style = any(not any(c in q["codes"] or any(len(c) >= 6 and c in k for k in q["codes"]) for q in prof if q is not p) for c in sh)   # Style steht in keiner anderen Kandidaten-Order
        if qx:
            if _qty_close(qx, p["total"]):
                score += W["menge_total"]; hits.append("Menge %d = Order %d Stk" % (qx, p["total"])); qty_total = True
            elif any(_qty_close(qx, q) and (iw & evw) for q, iw in p["item_qty"]):   # Positionsmenge nur, wenn der Text auch die Produktart nennt (T-Shirt, Hoodie ...)
                score += W["menge_pos"]; hits.append("Menge %d = eine Position" % qx); qty_pos = True
        uw = sorted(w for w in f["words"] if df.get(w) == 1 and w in (p["title_w"] | p["item_w"]) and w not in vwords and (len(w) >= 5 or w in PROGRAM_OK))
        if uw:
            score += min(WORD_CAP, W["wort"] * len(uw)); hits.append("Wort '%s'" % "', '".join(uw[:3]))
        nw = sorted(w for w in f["words"] if w in p["note_w"] and w not in (p["title_w"] | p["item_w"]) and w not in vwords and sum(1 for q in prof if w in q["note_w"] or w in q["title_w"] or w in q["item_w"]) == 1 and len(w) >= 6)
        if nw:
            score += W["wort_notiz"]; hits.append("Notiz-Wort '%s'" % nw[0])
        # belegbar = ein Treffer, der die Order wirklich von den anderen unterscheidet: Style nur in dieser Order, Gesamtmenge, Positionsmenge mit Wort, oder zwei unterscheidende Woerter
        verif = uniq_style or qty_total or (qty_pos and bool(uw)) or len(uw) >= 2
        res.append((o, score, hits, verif))
    res.sort(key=lambda r: -r[1])
    rank = [(r[0].get("title"), r[1], r[2]) for r in res]
    top, second = res[0], res[1]
    why = None
    if top[1] < MIN_SCORE:
        why = "zu wenig Punkte (%d)" % top[1]
    elif top[1] - second[1] < MARGIN:
        why = "kein klarer Abstand (%d zu %d)" % (top[1], second[1])
    elif not top[3]:
        why = "kein belegbares Signal"
    else:
        # Widerspruch: Ereignis nennt Style/Menge, beides passt nicht zur besten Order, aber eine andere Order hat einen Treffer -> Abstand haette das schon abgefangen; hier die Order selbst pruefen
        tp = next(p for p in prof if p["id"] == top[0]["id"])
        if qx and codes and not any(c in tp["codes"] for c in codes) and not _qty_close(qx, tp["total"]) and not any(_qty_close(qx, q) for q, _w in tp["item_qty"]):
            why = "Widerspruch: Menge und Style passen nicht zur besten Order"
    if why:
        return None, None, {"reason": why, "ranking": rank[:3]}
    return top[0], "; ".join(top[2]), {"ranking": rank[:3], "score": top[1], "margin": top[1] - second[1]}
