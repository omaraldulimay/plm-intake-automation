"""Lernen von Lieferanten-Kennungen: nach EINER sicheren Zuordnung wird die Kennung (PO-/Rechnungs-/Vertrags-/BL-/Container-Nr) als Alias der Bestellung gespeichert.

Format output/intake/po_aliases.json: {"<Kennung>": "<Bestellungs-ID>" | "<Order-Titel>" (alt, von Hand) | "__mehrdeutig__"}.
Stark = Zuordnung ueber PO-Nr/Titel/Style/bekannte Kennung (why 'ok' oder 'alias') oder Beleg DELIVERY_DOC.
Schwach (vendor_only, vendor_title, thread, text, menge) lernt nie. Zeigt eine Kennung schon auf eine ANDERE Bestellung: Konflikt, Alias wird 'mehrdeutig' und nicht mehr benutzt.
"""
import re

from plm_intake import core

AMBIG = "__mehrdeutig__"
STRONG = ("ok", "alias")
MIN_LEN = 5
ID_KEYS = ("invoice_number", "bl", "awb", "hbl", "mbl", "container")
DATE = re.compile(r"^(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})$")


def resolve(value, orders):
    """Alias-Wert (ID oder Titel) -> Order oder None."""
    for o in orders:
        if o.get("id") == value or (o.get("title") and core.norm(o["title"]) == core.norm(value)):
            return o
    return None


def lookup(aliases, key, orders):
    """-> (order|None, mehrdeutig:bool) fuer eine Kennung (exakt normalisiert)."""
    nk = core.norm(key)
    for a, v in (aliases or {}).items():
        if core.norm(a) == nk and nk:
            return (None, True) if v == AMBIG else (resolve(v, orders), False)
    return None, False


def valid(raw, order, extra_bad=(), others=()):
    """Darf diese Kennung als Alias gelernt werden?"""
    raw = str(raw or "").strip()
    n = core.norm(raw)
    if len(n) < MIN_LEN or DATE.match(raw) or re.fullmatch(r"\d{8}", n):
        return False
    if n in {core.norm(x) for x in extra_bad if x}:
        return False
    if n in (core.norm(order.get("poNumber")), core.norm(order.get("title"))):   # steht eh schon am Objekt
        return False
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", raw):   # Menge 85.290
        return False
    toks = [t for t in re.split(r"[^A-Za-z0-9]+", raw) if t]
    pre = {core.norm("".join(toks[:i])) for i in range(2, len(toks) + 1)} | {n}   # Vertragsmuster: Kennung oder ihr Anfang aus >= 2 Teilen ('26WJD-107' aus '26WJD-107-SMILODOX')
    own = [core.norm(order.get("title")), core.norm(order.get("poNumber"))]
    for o2 in others:   # steht im Titel/PO-Nr einer ANDEREN Bestellung (z. B. PO-LIEFERANT_AA-26WJD-107-SS26-1ST-ORDER), nicht aber in der eigenen
        if o2.get("id") == order.get("id"):
            continue
        for f in (core.norm(o2.get("title")), core.norm(o2.get("poNumber"))):
            if f and any(len(p) >= MIN_LEN and p in f and not any(p in x for x in own if x) for p in pre):
                return False
    for it in order.get("items") or []:   # Stylecode / Positionsname
        sku = core.norm(it["product"].get("sku")) if isinstance(it.get("product"), dict) else ""
        if n in core.norm(it.get("name")) or (sku and (n == sku or sku.startswith(n))):
            return False
    return True


def event_idents(e):
    ref, d = e.get("ref") or {}, e.get("details") or {}
    out = [ref.get("po_number"), ref.get("container")] + [d.get(k) for k in ID_KEYS]
    toks = []
    for x in out:   # Listen ('A, B, C') in Einzelkennungen zerlegen; nur Zeichen einer Kennung
        toks += [t for t in re.split(r"[,;\s]+", str(x or "")) if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/\-]*", t)]
    return toks


def candidates(assigned, rows, orders_by_id):
    """-> [(Kennung, order_id, Quelle)] nur aus starken Zuordnungen."""
    out = []
    others = list(orders_by_id.values())
    for e, oid, why in assigned:
        if why not in STRONG or oid not in orders_by_id:
            continue
        ref = e.get("ref") or {}
        bad = [ref.get("style")] + list((e.get("details") or {}).get(k) for k in ("qty", "quantity", "pieces", "total_pieces"))
        for i in event_idents(e):
            if valid(i, orders_by_id[oid], bad, others):
                out.append((i, oid, "Ereignis"))
    for r in rows or []:
        if r.get("kind") != "DELIVERY_DOC" or not r.get("pid") or r["pid"] not in orders_by_id:
            continue
        doc = r.get("doc") or {}
        for i in (doc.get("po_number"), doc.get("invoice_number")):
            if i and valid(i, orders_by_id[r["pid"]], (), others):
                out.append((str(i).strip(), r["pid"], "Beleg"))
    return out


def learn(aliases, assigned, rows, orders, apply=False):
    """Gibt (neue_aliases, neu:list, konflikte:list) zurueck. Aendert `aliases` nur bei apply=True (Trockenlauf lernt nichts, rechnet aber die Vorschau)."""
    by_id = {o["id"]: o for o in orders}
    work = dict(aliases or {})
    new, conflicts = [], []
    for key, oid, src in candidates(assigned, rows, by_id):
        nk = core.norm(key)
        cur_key = next((a for a in work if core.norm(a) == nk), None)
        if cur_key is None:
            work[key] = oid
            new.append((key, oid, src))
            continue
        if work[cur_key] == AMBIG:
            continue
        cur = resolve(work[cur_key], orders)
        if cur is not None and cur["id"] == oid:
            continue
        if cur is None:   # Altwert zeigt auf keine bekannte Order: nicht anfassen
            continue
        conflicts.append((key, cur["title"], by_id[oid]["title"]))
        work[cur_key] = AMBIG
    if apply:
        aliases.clear(); aliases.update(work)
    return work, new, conflicts


def report_lines(new, conflicts, apply):
    L = ["## Gelernte Aliase (%s)" % ("gespeichert" if apply else "Vorschau, nichts gespeichert")]
    L += ["- %s -> %s (%s)" % (k, oid, s) for k, oid, s in new] or ["- keine neuen"]
    if conflicts:
        L += ["", "## Alias-Konflikte (Kennung auf 2 Bestellungen, auf mehrdeutig gesetzt)"]
        L += ["- %s: %s <-> %s" % c for c in conflicts]
    return L
