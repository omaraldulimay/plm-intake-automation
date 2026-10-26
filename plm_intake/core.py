"""Pruef- und Baulogik fuer das Einpflegen von POs ins Lifecycle-PLM. Reine Funktionen, keine Netzzugriffe (testbar).

Eingabe (ausgelesene PO, Format siehe SCHEMA unten) + Kontext (Vendors, Produkte, bestehende Orders)
-> Ergebnis(decision, payload, issues). decision: CREATE | UPDATE | SKIP | BLOCK.
"""
import datetime as dt
import re
from dataclasses import dataclass, field

SCHEMA = """{
 "source": {"doc": "PI XW-SM260513", "mail_id": "...", "files": ["..."]},
 "vendor": "Lieferant C Co., Ltd.",
 "po_number": "XW-SM260513",
 "currency": "USD",
 "ex_factory": "2026-09-15", "etd": "2026-09-27",
 "items": [{"sku": "XW-041", "name": "XW-041 Men Windbreaker",
            "variants": [{"color": "Black", "price": 11.8, "sizes": {"S": 314, "M": 902}}]}],
 "payments": [{"name": "30% Deposit", "status": "Paid", "amount": 52464.0, "due": "2026-08-01", "terms": "30% deposit"}],
 "total_cost": 176626.65, "total_pieces": 18587,     # optional; sonst aus Positionen
 "contract_total": 174880.0,                          # optional; vereinbarter Wert (Teillieferung/Mehrmenge)
 "notes": "freier Text", "open": ["Anzahlungsdatum unbekannt"]
}"""

CURRENCIES = {"USD", "EUR", "GBP", "CNY", "TRY"}
PLACEHOLDER_SIZE = "ONE SIZE"
TOL = 0.01          # Euro/Dollar-Toleranz bei Summen
LEGAL = {"co", "ltd", "limited", "inc", "gmbh", "kg", "llc", "pvt", "private", "company", "corp", "sp", "zoo", "san", "tic", "as", "sti",
         "sanayi", "ticaret", "anonim", "sirketi", "ve", "a", "s", "and"}   # tuerkische Rechtsform: "Sanayi ve Ticaret Anonim Sirketi"
GENERIC = {"textile", "textiles", "tekstil", "sport", "sports", "industry", "trading", "trade", "group", "garment", "enterprise", "enterprises",
           "china", "hong", "kong", "outdoor", "housewares", "company", "international"}

COLOR_ALIASES = {
    "schwarz": "black", "weiss": "white", "weiß": "white", "grau": "grey", "gray": "grey", "dunkelblau": "navy",
    "marine": "navy", "creme": "cream", "anthrazit": "anthracite", "anthrazite": "anthracite", "gelb": "yellow",
    "rot": "red", "blau": "blue", "gruen": "green", "grün": "green", "braun": "brown",
}
# Groessen-Klassen: alles in einer Gruppe gilt als gleich (Produkt im PLM heisst z. B. 2XL oder XXL, 3XXL fuer 3XL)
SIZE_CLASSES = [{"XXS", "2XS"}, {"XXL", "2XL"}, {"3XL", "XXXL", "3XXL"}, {"4XL", "XXXXL", "4XXL"}, {"ONE SIZE", "ONESIZE", "OS", "UNI"}]
BANK_PATTERNS = [r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b", r"\bSWIFT\b", r"\bIBAN\b", r"\bBIC\b\s*[:\-]?\s*[A-Z0-9]{8}",
                 r"(?i)beneficiary.{0,10}a/?c", r"(?i)account\s*(no|number|nr)"]


@dataclass
class Issue:
    level: str   # ERROR | WARN | INFO
    code: str
    msg: str


@dataclass
class Result:
    decision: str = "BLOCK"
    payload: dict = None
    issues: list = field(default_factory=list)
    existing_id: str = None
    stats: dict = field(default_factory=dict)
    product_specs: list = field(default_factory=list)

    def errors(self): return [i for i in self.issues if i.level == "ERROR"]


# ---------- Normalisierung ----------
def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _ascii(text):
    """Tuerkische/diakritische Zeichen vereinfachen (TEKSTIL = TEKSTIL mit Punkt-I, Sirketi mit Cedille), damit Namensvarianten gleich tokenisiert werden."""
    import unicodedata
    t = str(text or "").replace("\u0131", "i").replace("\u0130", "I")
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def vendor_tokens(name):
    toks = re.findall(r"[a-z0-9]+", _ascii(name).lower())
    return [t for t in toks if t not in LEGAL]


def alias_key(name):
    """Firmenkern ohne Rechtsform/Allerweltswoerter, ASCII, zusammengeschrieben (nur fuer den Alias-Abgleich)."""
    return "".join(t for t in vendor_tokens(name) if t not in GENERIC)


def match_vendor(name, vendors, aliases=None):
    """Eindeutigen Vendor finden. Rueckgabe (vendor|None, grund).
    Reihenfolge: Alias-Tabelle (von Menschen gepflegt) > exakt (normalisiert) > gleicher Namenskern > eindeutiger Teilstring (>=4 Zeichen).
    Mehrdeutigkeit = kein Treffer (lieber Review als falscher Lieferant)."""
    n = norm(name)
    ck = alias_key(name)
    for alias, target in (aliases or {}).items():
        if norm(alias) == n or (len(ck) >= 5 and alias_key(alias) == ck):   # auch Kurzformen/Schreibvarianten: 'SANAYI VE TIC. LTD. STI.' = 'SANAYI VE TICARET LIMITED SIRKETI'
            hit = [v for v in vendors if v["id"] == target or norm(v["name"]) == norm(target)]
            if len(hit) == 1:
                return hit[0], "alias"
    exact = [v for v in vendors if norm(v["name"]) == n]
    if len(exact) == 1:
        return exact[0], "exact"
    toks = set(vendor_tokens(name))
    core = toks - GENERIC
    best = []
    for v in vendors:
        vcore = set(vendor_tokens(v["name"])) - GENERIC
        if core and vcore and (core == vcore or ((core <= vcore or vcore <= core) and len(core & vcore) >= 2)):
            best.append(v)
    if len(best) == 1:
        return best[0], "fuzzy"
    if not best:
        key = "".join(sorted(core, key=lambda t: toks_order(name, t))) if core else ""
        if len(key) >= 4:
            sub = [v for v in vendors if key in "".join(sorted(set(vendor_tokens(v["name"])) - GENERIC, key=lambda t: toks_order(v["name"], t)))]
            if len(sub) == 1:
                return sub[0], "fuzzy"
            if len(sub) > 1:
                best = sub
    return None, ("mehrdeutig: " + ", ".join(v["name"] for v in best)) if best else "nicht gefunden"


def toks_order(name, t):
    return str(name or "").lower().find(t)


def norm_color(c):
    c = re.sub(r"\([^)]*\)", " ", str(c or "")).strip().lower()   # Zusaetze in Klammern ("Schwarz (GT0301-A1)", "Wine Red (former Bordeaux)")
    c = re.sub(r"\b\d{2}-\d{4}\s?[a-z]{2,3}\b", "", c)       # Pantone/TCX-Codes entfernen
    c = re.sub(r"(\D)\d{2}-\d{4}.*$", r"\1", c)               # 'navy19-3815tcx'
    c = re.sub(r"[^a-zäöüß ]", "", c).strip()
    return COLOR_ALIASES.get(c, c)


def size_class(s):
    u = str(s or "").strip().upper().replace(" ", "")
    for grp in SIZE_CLASSES:
        if u in {g.replace(" ", "") for g in grp}:
            return frozenset(g.replace(" ", "") for g in grp)
    return frozenset([u])


def map_size(size, product_sizes):
    """Groesse auf den im PLM-Produkt verwendeten Namen abbilden. None = nicht abbildbar."""
    if not product_sizes:
        return None
    for ps in product_sizes:
        if str(ps).strip().upper() == str(size).strip().upper():
            return ps
    cls = size_class(size)
    hits = [ps for ps in product_sizes if str(ps).strip().upper().replace(" ", "") in cls]
    return hits[0] if len(hits) == 1 else None


def parse_date(v):
    """ISO, DD.MM.YYYY, DD/Mon/YY, DD/MM/YYYY -> date | None"""
    if v in (None, ""):
        return None
    if isinstance(v, (dt.date, dt.datetime)):
        return v if isinstance(v, dt.date) and not isinstance(v, dt.datetime) else v.date()
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%b/%y", "%d/%b/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def iso(d): return d.strftime("%Y-%m-%dT00:00:00.000Z")
def ms(d): return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
def r2(x): return round(float(x) + 1e-9, 2)


def po_key(vendor_id, po_number): return (vendor_id, norm(po_number))


def make_title(vendor_name, po_number):
    toks = vendor_tokens(vendor_name)
    short = "".join(toks[:2]).upper() or "VENDOR"
    num = re.sub(r"[^A-Za-z0-9\-]+", "-", str(po_number).strip()).strip("-")
    n = norm(po_number)
    if n and any(len(norm(t)) >= 3 and n.startswith(norm(t)) for t in [short] + toks[:3]):   # Nummer beginnt schon mit dem Lieferantenkuerzel (LIEFERANT_D-ALI..): nicht verdoppeln (wie bei den migrierten POs)
        return ("PO-%s" % num).upper()
    return ("PO-%s-%s" % (short, num)).upper()


def find_parent(vendor_id, po_number, orders):
    """Bestell-PO, zu der ein Beleg gehoert: PO-Nr der Bestellung ist Anfang der Beleg-Nr (z. B. LIEFERANT_D-ALI20260821 -> LIEFERANT_D-ALI20260821-SEA) oder umgekehrt; nur beim selben Lieferanten."""
    n = norm(po_number)
    if len(n) < 6:
        return None
    best = None
    for o in orders:
        mid = o.get("manufacturer", {}).get("id") if isinstance(o.get("manufacturer"), dict) else o.get("manufacturer")
        if mid != vendor_id:
            continue
        for key in (norm(o.get("poNumber")), norm(re.sub(r"^PO-?", "", str(o.get("title") or ""), flags=re.I))):
            if len(key) >= 6 and (n.startswith(key) or key.startswith(n)):
                if best is None or len(key) > best[0]:
                    best = (len(key), o)
    return best[1] if best else None


def item_sku_token(name):
    m = re.match(r"\s*([A-Za-z]{1,6}\d*[-_ ]?\d{2,}[A-Za-z]?(?:-\d+)?)", str(name or ""))
    return norm(m.group(1)) if m else ""


_STYLE_RX = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{1,6}(?:\d{2,}|(?:[-_][A-Za-z0-9]{1,6})*[-_]\d{2,})[A-Za-z]?(?:-\d+)*)(?![A-Za-z0-9])|(?<![A-Za-z0-9])(\d{5,6})(?![A-Za-z0-9])")


def style_tokens(name):
    """ALLE Stylenummern in einem Positionsnamen (normalisiert): am Anfang, in Klammern ('(ALP-103, ...)') und reine 5-6-stellige Nummern ('26498 Men Hoodie')."""
    out = set()
    for m in _STYLE_RX.finditer(str(name or "")):
        t = norm(m.group(1) or m.group(2))
        if len(t) >= 5:
            out.add(t)
    first = item_sku_token(name)
    if first:
        out.add(first)
    return out


def order_styles(o, products_by_id):
    """Styles (normalisierte SKUs) einer bestehenden Order: aus den Positionsnamen und den verknuepften Produkten."""
    out = set()
    for it in o.get("items") or []:
        out |= style_tokens(it.get("name"))
        pid = it.get("product")
        pid = pid.get("id") if isinstance(pid, dict) else pid
        if pid and products_by_id.get(pid):
            out.add(norm(products_by_id[pid]))
    return out


QTY_HIGH, QTY_LOW, COVER_MIN = 1.5, 0.67, 0.5


def style_covered(style, theirs):
    """Style (normalisiert) steckt in den Styles der Order: exakt oder Variantenschreibweise (gleicher Anfang, mind. 5 Zeichen)."""
    return style in theirs or any(len(t) >= 5 and len(style) >= 5 and (style.startswith(t) or t.startswith(style)) for t in theirs)


def clear_mismatch(pieces, order_pieces, wanted, theirs):
    """Zuordnungspruefung fuer SCHWACHE Wege (kein PO-Nr-Treffer, nur Lieferant/Style/'einzige laufende Order'): weichen Menge UND Styles klar ab?
    Menge klar anders = Beleg-Menge > 1,5x oder < 0,67x der Order-Menge; Styles klar anders = weniger als 50 % der Beleg-Styles kommen in der Order vor.
    Nur wenn beides zutrifft (eine Teillieferung mit denselben Styles oder ein Beleg ueber alle Styles in anderer Menge bleibt zuordenbar). Unbekannte Menge/Styles = False.
    -> (bool, Text)"""
    try:
        pieces, order_pieces = float(pieces or 0), float(order_pieces or 0)
    except (TypeError, ValueError):
        return False, ""
    wanted = {w for w in wanted or () if w}
    if pieces <= 0 or order_pieces <= 0 or not wanted:
        return False, ""
    ratio = pieces / order_pieces
    cover = sum(1 for w in wanted if style_covered(w, theirs or set())) / len(wanted)
    off = (ratio > QTY_HIGH or ratio < QTY_LOW) and cover < COVER_MIN
    return off, "Menge %d Stk vs. Order %d Stk (%.2fx), Style-Ueberdeckung %d %%" % (pieces, order_pieces, ratio, round(cover * 100))


def find_style_overlap(vendor_id, items, orders, products):
    """Bestehende Order DESSELBEN Lieferanten mit mindestens einem gleichen Style -> (Order, Styles) oder None."""
    by_id = {p["id"]: p.get("sku") for p in products or [] if p.get("sku")}
    mine = {norm(i.get("sku")) for i in items if i.get("sku")}
    for i in items:
        mine |= style_tokens(i.get("name"))
    mine.discard("")
    for o in orders:
        mid = o.get("manufacturer", {}).get("id") if isinstance(o.get("manufacturer"), dict) else o.get("manufacturer")
        if mid != vendor_id:
            continue
        theirs = order_styles(o, by_id)
        # exakt ODER Variantenschreibweise: 'HY29582-Z-A' gehoert zum Basisstyle 'HY29582' (gleicher Anfang, mind. 5 Zeichen)
        common = {m for m in mine if m in theirs or any(len(t) >= 5 and (m.startswith(t) or t.startswith(m)) for t in theirs)}
        if common:
            return o, sorted(common)
    return None


def po_in_title(po_number, title):
    """PO-Nr steckt im Titel, aber NICHT als Anfang einer laengeren Nummer ('...-DE-EA-2' darf nicht '...-DE-EA-2EXTRA' treffen):
    entweder steht sie am Ende des Titels oder als eigenes Token (Rand: kein Buchstabe/keine Ziffer davor und danach)."""
    n, t = norm(po_number), norm(title)
    if not n or n not in t:
        return False
    if t.endswith(n):
        return True
    raw = str(po_number or "").strip().lower()
    return bool(raw) and re.search(r"(?<![a-z0-9])" + re.escape(raw) + r"(?![a-z0-9])", str(title or "").lower()) is not None


def find_existing(vendor_id, po_number, title, total_cost, pieces, orders):
    """Bestehende Order suchen: (1) PO-Nr, (2) PO-Nr im Titel, (3) gleicher Titel, (4) gleicher Vendor+Summe+Stueckzahl."""
    n = norm(po_number)
    for o in orders:
        mid = o.get("manufacturer", {}).get("id") if isinstance(o.get("manufacturer"), dict) else o.get("manufacturer")
        same_vendor = mid == vendor_id
        if n and norm(o.get("poNumber")) == n and same_vendor:
            return o, "PO-Nr"
        if n and len(n) >= 5 and same_vendor and po_in_title(po_number, o.get("title")):
            return o, "PO-Nr im Titel"
        if norm(o.get("title")) == norm(title):
            return o, "Titel"
        if same_vendor and total_cost > 0 and abs((o.get("totalCost") or 0) - total_cost) <= TOL and o.get("totalNumberOfPieces") == pieces:
            return o, "Vendor+Summe+Stueckzahl"
    return None, None


# ---------- Hauptfunktion ----------
MIN_PIECES = 10


def build(po, ctx, today=None, force_create=False):
    """po: ausgelesene PO; ctx: {'vendors': [...], 'products': [...], 'orders': [...]}"""
    res = Result()
    add = lambda lvl, code, msg: res.issues.append(Issue(lvl, code, msg))
    today = today or dt.date.today()

    # Grundfelder
    if not po.get("vendor"):
        add("ERROR", "vendor_missing", "Kein Lieferant in den ausgelesenen Daten")
    if not str(po.get("po_number") or "").strip():
        add("ERROR", "po_number_missing", "Keine PO-/PI-Nummer; ohne Nummer keine sichere Dubletten-Pruefung")
    cur = str(po.get("currency") or "").upper()
    if cur not in CURRENCIES:
        add("ERROR", "currency", "Waehrung '%s' unbekannt (erlaubt: %s)" % (cur or "-", ", ".join(sorted(CURRENCIES))))
    vendor = None
    if po.get("vendor"):
        vendor, why = match_vendor(po["vendor"], ctx["vendors"], ctx.get("aliases"))
        if not vendor:
            add("ERROR", "vendor_unknown", "Vorgaenger fehlt: Vendor '%s' (%s). Erst Vendor anlegen/zuordnen" % (po["vendor"], why))
        elif why == "fuzzy":
            add("WARN", "vendor_fuzzy", "Vendor '%s' per Namensaehnlichkeit zu '%s' zugeordnet" % (po["vendor"], vendor["name"]))

    # Positionen
    open_items = list(po.get("open") or [])
    price_missing = False
    items, total_cost, total_pieces = [], 0.0, 0
    specs = []
    products = ctx.get("products") or []
    by_sku = {norm(p.get("sku")): p for p in products if p.get("sku")}
    if not po.get("items"):
        add("ERROR", "no_items", "Keine Positionen")
    for it in po.get("items") or []:
        name = item_display_name(it)
        prod = by_sku.get(norm(it.get("sku"))) if it.get("sku") else None
        if it.get("sku") and not prod:
            add("INFO", "product_unlinked", "Produkt '%s' nicht im PLM: Position ohne Produktlink" % it["sku"])
            open_items.append("Produkt %s ohne Verknuepfung" % it["sku"])
        pvars = {norm_color(v["name"]): v for v in (prod.get("variants") or [])} if prod else {}
        psizes = prod.get("sizes") if prod else None
        out_vars = []
        for v in it.get("variants") or []:
            color = v.get("color") or "Default Style"
            price = v.get("price")
            if price is None or float(price) == 0:   # kein belegter Stueckpreis: Order wird trotzdem angelegt (Preis 0), Preis kommt spaeter per Proforma/Rechnung (price_fill)
                price = 0.0
                price_missing = True
                add("WARN", "price_missing", "Preis fehlt (%s %s): Preis 0 gesetzt, PREIS AUSSTEHEND" % (name, color))
            if price < 0:
                add("ERROR", "price_negative", "Negativer Preis bei %s %s" % (name, color))
            amounts = []
            sizes = v.get("sizes") or {}
            if not sizes:
                add("WARN", "sizes_missing", "Keine Groessenverteilung (%s %s): ONE SIZE" % (name, color))
                open_items.append("Groessenverteilung fehlt: %s %s" % (name, color))
                sizes = {PLACEHOLDER_SIZE: v.get("quantity") or 0}
            seen = {}
            for size, q in sizes.items():
                if q is None or float(q) == 0:
                    continue
                if float(q) < 0 or float(q) != int(float(q)):
                    add("ERROR", "qty_invalid", "Ungueltige Menge %s bei %s %s %s" % (q, name, color, size))
                    continue
                q = int(q)
                key = size
                if psizes is not None:
                    mapped = map_size(size, psizes) if size != PLACEHOLDER_SIZE else None
                    if mapped:
                        key = mapped
                    elif size != PLACEHOLDER_SIZE:
                        add("WARN", "size_unmapped", "Groesse '%s' (%s %s) passt zu keiner Produktgroesse %s" % (size, name, color, psizes))
                seen[key] = seen.get(key, 0) + q
            for key, q in seen.items():
                cost = r2(q * price)
                amounts.append({"key": key, "quantity": q, "price": price, "cost": cost})
                total_cost += cost
                total_pieces += q
            if not amounts:
                add("WARN", "variant_empty", "Variante ohne Mengen verworfen: %s %s" % (name, color))
                continue
            ov = {"name": color, "amounts": amounts}
            if prod:
                pv = pvars.get(norm_color(color))
                if pv:
                    ov["variantId"] = pv["id"]
                else:
                    add("WARN", "color_unlinked", "Farbe '%s' nicht an Produkt %s: Variante ohne variantId" % (color, prod.get("sku")))
            out_vars.append(ov)
        oi = {"name": name, "variants": out_vars}
        pi = it.get("product_info")
        if pi and pi.get("barcode") and not valid_ean(pi["barcode"]):
            add("WARN", "barcode_invalid", "Barcode '%s' (%s) hat keine gueltige Pruefziffer: nicht ins PLM, in Offen vermerkt" % (pi["barcode"], it.get("sku")))
            open_items.append("Barcode %s ungueltig (%s)" % (pi["barcode"], it.get("sku")))
            pi = {k: v for k, v in pi.items() if k != "barcode"}
        if pi and it.get("sku"):
            specs.append({"sku": it["sku"], "linked_product": prod["id"] if prod else None,
                          **{k: v for k, v in pi.items() if v not in (None, "", [])}})
        if prod:
            oi["product"] = prod["id"]
        items.append(oi)
    total_cost = r2(total_cost)

    # Summen gegen Quelle
    # Harte Sperren: leere Bestellung / Kleinstbeleg (Muster) nie anlegen
    if price_missing:
        open_items.append("PREIS AUSSTEHEND (Beleg ohne Preis, Stand %s)" % today)
    if total_pieces == 0 or (total_cost == 0 and not price_missing and (po.get("total_cost") or 0) > 0):
        add("ERROR", "empty_order", "Positionen ergeben %d Stk / %.2f (laut Beleg %s Stk / %s): leere Bestellung wird nicht angelegt" % (total_pieces, total_cost, po.get("total_pieces"), po.get("total_cost")))
    elif total_pieces < MIN_PIECES:
        add("ERROR", "too_small", "Nur %d Stk insgesamt (unter %d): Muster/Kleinstbeleg, keine Bestellung" % (total_pieces, MIN_PIECES))
    if po.get("total_cost") is not None and not (price_missing and total_cost == 0) and round(abs(r2(po["total_cost"]) - total_cost), 2) > TOL:
        add("WARN", "sum_mismatch", "Positionen %.2f != angegebener Gesamtwert %.2f" % (total_cost, po["total_cost"]))
        open_items.append("UNSTIMMIG: Positionen %.2f != Gesamtwert laut Beleg %.2f (%+.2f), Quelle pruefen (moeglicherweise Lesefehler)" % (total_cost, po["total_cost"], total_cost - r2(po["total_cost"])))
    if po.get("total_pieces") is not None and int(po["total_pieces"]) != total_pieces:
        add("WARN", "pieces_mismatch", "Positionen %d Stk != angegeben %d Stk" % (total_pieces, po["total_pieces"]))
        open_items.append("UNSTIMMIG: Positionen %d Stk != laut Beleg %d Stk (%+d), Quelle pruefen (moeglicherweise Lesefehler)" % (total_pieces, int(po["total_pieces"]), total_pieces - int(po["total_pieces"])))
    contract = po.get("contract_total")
    if contract and round(abs(total_cost - r2(contract)), 2) > TOL:
        diff = total_cost - r2(contract)
        add("WARN", "contract_diff", "Positionen %.2f vs. vereinbart %.2f (%+.2f): Mehr-/Mindermenge in Notes" % (total_cost, contract, diff))
        open_items.append("Abweichung zum vereinbarten Wert %.2f: %+.2f" % (contract, diff))

    # Zahlungen
    d_ex, d_etd = parse_date(po.get("ex_factory")), parse_date(po.get("etd"))
    for label, raw, d in (("ex_factory", po.get("ex_factory"), d_ex), ("etd", po.get("etd"), d_etd)):
        if raw not in (None, "") and d is None:
            add("WARN", "date_invalid", "Datum '%s' (%s) nicht lesbar: weggelassen" % (raw, label))
            open_items.append("%s nicht lesbar" % label)
    placeholder = d_ex or d_etd or today
    pays, psum = [], 0.0
    for p in po.get("payments") or []:
        amt = r2(p.get("amount") or 0)
        if amt < 0:
            add("ERROR", "payment_negative", "Negative Zahlung '%s'" % p.get("name"))
        status = p.get("status") or "Unpaid"
        if status not in ("Paid", "Unpaid"):
            add("ERROR", "payment_status", "Zahlungsstatus '%s' ungueltig (Paid|Unpaid)" % status)
        due = parse_date(p.get("due"))
        if due is None:
            due = placeholder
            open_items.append("Zahlungstermin Platzhalter: %s" % p.get("name"))
            add("INFO", "due_placeholder", "Zahlungstermin '%s' unbekannt: Platzhalter %s" % (p.get("name"), due))
        pays.append({"name": p.get("name") or "Zahlung", "status": status, "amount": amt, "dueDate": ms(due), "terms": p.get("terms") or ""})
        psum += amt
    if not pays and total_cost > 0:
        add("WARN", "no_payments", "Keine Zahlungen angegeben: Platzhalter-Zahlung ueber Gesamtbetrag")
        open_items.append("Zahlungsbedingungen unbekannt")
        pays = [{"name": "Gesamtbetrag (Platzhalter)", "status": "Unpaid", "amount": total_cost, "dueDate": ms(placeholder), "terms": ""}]
        psum = total_cost
    if pays and round(abs(r2(psum) - total_cost), 2) > TOL:
        add("WARN", "payment_sum", "Zahlungen %.2f != Gesamtwert %.2f" % (psum, total_cost))
        open_items.append("UNSTIMMIG: Zahlungen %.2f != Gesamtwert %.2f (%+.2f), Zahlungsplan pruefen" % (psum, total_cost, psum - total_cost))

    # Notes + Bankdaten-Sperre
    notes = _notes(po, open_items)
    for pat in BANK_PATTERNS:
        if re.search(pat, notes):
            add("ERROR", "bank_data", "Bankdaten/IBAN/Swift in Notes erkannt: nicht ins PLM (Muster %s)" % pat)
            break

    # Payload
    title = po.get("title") or make_title(po.get("vendor") or "", po.get("po_number") or "")
    payload = {"title": title, "manufacturer": vendor["id"] if vendor else None, "currency": cur, "poNumber": str(po.get("po_number") or ""),
               "useCustomPoNumber": True, "notes": notes, "items": items, "payments": pays, "totalCost": total_cost,
               "totalNumberOfPieces": total_pieces, "assignees": []}
    res.product_specs = specs
    if d_ex: payload["exFactoryExpectedDate"] = iso(d_ex)
    if d_etd: payload["etdEstimatedDate"] = iso(d_etd)
    res.payload = payload
    res.stats = {"items": len(items), "variants": sum(len(i["variants"]) for i in items), "pieces": total_pieces, "total": total_cost}

    # Fehlende PO-Nr ist KEIN Blocker, wenn es beim selben Lieferanten schon eine Order mit identischer Summe und Stueckzahl gibt (die PI wurde nur ohne Nummer gelesen): dann Dublette
    if vendor and any(i.code == "po_number_missing" for i in res.issues) and total_cost > 0:
        twin = [o for o in ctx.get("orders") or [] if (o.get("manufacturer", {}).get("id") if isinstance(o.get("manufacturer"), dict) else o.get("manufacturer")) == vendor["id"]
                and abs((o.get("totalCost") or 0) - total_cost) <= TOL and o.get("totalNumberOfPieces") == total_pieces]
        if len(twin) == 1:
            res.issues = [i for i in res.issues if i.code != "po_number_missing"]
            add("INFO", "po_number_missing_duplicate", "PO-Nr fehlt im Beleg, aber Order #%s hat identische Summe/Stueckzahl: als Dublette behandelt" % twin[0].get("orderNumber"))

    # Dubletten-/Update-Entscheidung (nur wenn Vendor bekannt)
    if vendor and not res.errors():
        ex, how = find_existing(vendor["id"], po.get("po_number"), title, total_cost, total_pieces, ctx.get("orders") or [])
        if ex:
            res.existing_id = ex.get("id")
            same = abs((ex.get("totalCost") or 0) - total_cost) <= TOL and ex.get("totalNumberOfPieces") == total_pieces
            if same:
                res.decision = "SKIP"
                add("INFO", "duplicate", "Existiert schon (#%s, gefunden ueber %s), Daten identisch: nichts tun" % (ex.get("orderNumber"), how))
            else:
                res.decision = "UPDATE"
                add("WARN", "exists_changed", "Existiert (#%s, %s) mit anderer Summe/Stueckzahl (PLM %s Stk / %s, neu %d Stk / %.2f): UPDATE nach Backup, kein Neuanlegen"
                    % (ex.get("orderNumber"), how, ex.get("totalNumberOfPieces"), ex.get("totalCost"), total_pieces, total_cost))
            return res
        dt_ = str(po.get("doc_type") or "").upper()
        if dt_ in ("PACKING_LIST", "INVOICE"):
            # Rechnung/Packliste = Beleg zu einer Lieferung einer BESTEHENDEN Bestellung, keine neue Bestellung (Teillieferungen wie -SEA/-AIR/-TRAIN
            # derselben PI wuerden sonst als Dubletten angelegt). Nie automatisch anlegen; Eltern-PO nennen, wenn erkennbar.
            parent = find_parent(vendor["id"], po.get("po_number"), ctx.get("orders") or [])
            hint = " Gehoert vermutlich zu Order #%s %s." % (parent.get("orderNumber"), parent.get("title")) if parent else " Passende Bestell-PO im PLM nicht gefunden."
            add("WARN", "delivery_document_only", "%s ist ein Beleg zu einer Lieferung, keine neue Bestellung: nicht anlegen.%s" % ("Rechnung" if dt_ == "INVOICE" else "Packliste", hint))
            res.decision = "BLOCK"
            res.existing_id = parent.get("id") if parent else None
            return res
        ov = find_style_overlap(vendor["id"], po.get("items") or [], ctx.get("orders") or [], ctx.get("products") or [])
        if ov:
            add("WARN", "style_overlap", "Lieferant hat schon Order #%s %s mit denselben Styles (%s): Reorder oder Teil derselben Bestellung? Mensch entscheidet, nicht automatisch anlegen."
                % (ov[0].get("orderNumber"), ov[0].get("title"), ", ".join(ov[1][:4])))
            if not force_create:
                res.decision = "BLOCK"
                res.existing_id = ov[0].get("id")
                return res
            add("INFO", "style_overlap_forced", "Mensch hat CREATE entschieden (override): trotz gleicher Styles wie Order #%s neue Bestellung" % ov[0].get("orderNumber"))
        res.decision = "CREATE"
        return res
    res.decision = "BLOCK"
    return res


def item_display_name(it):
    """Positionsname MIT Stylenummer ('HY29583 MEN'S JACKET'), wie bei den migrierten POs; keine doppelte Nummer, wenn sie schon im Namen steht."""
    sku = re.sub(r"\s+", " ", str(it.get("sku") or "")).strip()
    name = re.sub(r"\s+", " ", str(it.get("name") or "")).strip()
    if sku and name and norm(sku) in norm(name):
        return name
    return ("%s %s" % (sku, name)).strip() or "?"


def valid_ean(code):
    """EAN-8/UPC-A/EAN-13/GTIN-14 mit Pruefziffer. Das PLM zeigt sonst 'invalid barcode'."""
    c = str(code or "").strip()
    if not c.isdigit() or len(c) not in (8, 12, 13, 14):
        return False
    body, chk = c[:-1], int(c[-1])
    tot = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - tot % 10) % 10 == chk


def _terms(po):
    """Zahlungsbedingungen kurz: 'Anzahlung 30%: 30% deposit; Rest 70%: 70% before shipment' (aus den Zahlungszeilen)."""
    out = []
    for p in po.get("payments") or []:
        t = re.sub(r"\s+", " ", str(p.get("terms") or "")).strip()
        n = re.sub(r"\s+", " ", str(p.get("name") or "")).strip()
        if n or t:
            out.append(("%s: %s" % (n, t)) if n and t and core_norm_ne(n, t) else (n or t))
    return "; ".join(out[:6])


def core_norm_ne(a, b):
    return norm(a) != norm(b)


def _notes(po, open_items):
    """Bestell-Kopf nach Best Practice (die PO hat nur wenige eigene Felder): Nummer/Dokumentart, Quelle samt Mail-Datum, PO-Datum, Incoterm, ETA, Lieferadresse,
    Zahlungsbedingungen, danach Lieferbedingungen/Besonderheiten aus dem Dokument und 'Offen'."""
    src = po.get("source") or {}
    parts = []
    dtp = str(po.get("doc_type") or "").upper()
    ref = " ".join(x for x in [dtp, str(po.get("po_number") or "").strip()] if x)
    q = [x for x in [src.get("doc"), ("Mail %s" % src["mail_id"]) if src.get("mail_id") else None] if x]
    head = "Quelle: " + ", ".join(([ref] if ref else []) + q)
    if src.get("mail_date"):
        head += " (Mail vom %s)" % str(src["mail_date"])[:16]
    if head != "Quelle: ":
        parts.append(head + ".")
    kv = [("PO-Datum", po.get("doc_date")), ("Incoterm", po.get("incoterm")), ("ETA", po.get("eta")), ("Lieferadresse", po.get("ship_to")), ("Zahlungsbedingungen", _terms(po))]
    kv = ["%s %s" % (k, v) for k, v in kv if v]
    if kv:
        parts.append(", ".join(kv) + ".")
    if po.get("notes"):
        parts.append(str(po["notes"]).strip())
    uniq = []
    for o in open_items:
        if o not in uniq:
            uniq.append(o)
    if uniq:
        parts.append("Offen: " + "; ".join(uniq) + ".")
    return " ".join(parts)
