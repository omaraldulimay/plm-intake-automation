"""Sendungen (Bereich "Shipments") aus Packlisten und Versand-Ereignissen pflegen. Schreibweg: REST POST/PUT /shipments (kein MCP noetig).

Prozess (Best Practice): Packliste/Verladebereitschaft -> Sendung "pending" mit den Mengen des BELEGS (Teilsendungen = eine Sendung je Beleg, z. B. LIEFERANT_D See/Luft/Bahn)
-> Meilenstein SHIPPED (B/L, AWB, Container verladen) -> "in_transit" + Tracking -> DELIVERED (Ware eingegangen) -> "delivered". Nie rueckwaerts, nie loeschen.
Nur bei EINDEUTIGER Order (PO-Nr belegt, nicht ueber den Lieferanten geraten). Idempotent: Marker "[doc:...]"/"[ev:...]" in den Notizen der Sendung.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402

RANK = {"pending": 1, "in_transit": 2, "delivered": 3}
MILESTONE_STATUS = {"SHIPPED": "in_transit", "DELIVERED": "delivered", "ARRIVED_WAREHOUSE": "delivered"}


def method_from_ref(po_number):
    """Beleg-Nr mit Endung SEA/AIR/TRAIN/RAIL/TRUCK (LIEFERANT_D-...-SEA) -> sea/air/ground, sonst None. Vorrang vor Freitext."""
    m = re.search(r"(?:^|[-_/ ])(sea|air|train|rail|truck|road|ground)\s*$", str(po_number or "").strip().lower())
    return {"sea": "sea", "air": "air", "train": "ground", "rail": "ground", "truck": "ground", "road": "ground", "ground": "ground"}[m.group(1)] if m else None


def is_packaging_doc(doc):
    """Packaging-/Label-Freigabe oder Planung statt Versandbeleg: dann keine Sendung."""
    n = " ".join(str(x) for x in (doc.get("notes"), doc.get("source", {}).get("doc"))).lower()
    approval = re.search(r"freigabe|approval|artwork|sticker|polybag|carton marks|keine rechnung|kein rechnungs", n)
    shipping = re.search(r"\bctns?\b|cartons?\s*\d|kartons|gross weight|g\.w\.|cbm|bl no|b/l|awb|container|vessel", n)
    return bool(approval and not shipping)


def guess_method(text, default="sea"):
    """(Methode, belegt?) aus Freitext: air | sea | ground."""
    t = str(text or "").lower()
    for m, pat in (("air", r"\bair\b|by air|awb|luftfracht|\bluft\b|express|dhl|ups|fedex"), ("sea", r"\bsea\b|vessel|ocean|see(?:fracht)?\b|container|b/l|bill of lading|shipping line"),
                   ("ground", r"train|rail|bahn|truck|road|lkw|ground|strasse|straße|trailer")):
        if re.search(pat, t):
            return m, True
    return default, False


_PHRASES = [("wine red", "bordeaux"), ("burgundy", "bordeaux"), ("dark blue", "darkblue"), ("dunkelblau", "darkblue"), ("navy", "darkblue"), ("marine", "darkblue"), ("dark green", "darkgreen"),
            ("dunkelgruen", "darkgreen"), ("grey melange", "greymelange"), ("gray melange", "greymelange"), ("grau melange", "greymelange"), ("light grey", "lightgrey"), ("hellgrau", "lightgrey")]
_WORDS = {"schwarz": "black", "siyah": "black", "weiss": "white", "beyaz": "white", "grau": "grey", "gray": "grey", "braun": "brown", "kahverengi": "brown", "rot": "red", "blau": "blue",
          "gruen": "green", "gelb": "yellow", "anthrazit": "anthracite", "creme": "cream", "ecru": "cream", "tuerkis": "turquoise", "rosa": "pink"}


def color_key(name):
    """Farbname -> Menge kanonischer Woerter (DE/EN/TR-Synonyme, ohne Codes in Klammern und TCX-Nummern)."""
    t = str(name or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\b\d{2}-\d{4}\s*(tcx|tpx|tpg)?\b", " ", t)
    for a, b in _PHRASES:
        t = t.replace(a, b)
    toks = {_WORDS.get(w, w) for w in re.findall(r"[a-z]+", t) if len(w) > 1}
    return toks - {"and", "und", "the", "tcx"}


def color_match(a, b):
    ka, kb = color_key(a), color_key(b)
    if not ka or not kb:
        return False
    return ka == kb or ka <= kb or kb <= ka


def order_lines(order):
    """Items der Order (aus GraphQL getOrderById) -> {produktId: {name, sku?, variants: {variantName(lower): {id, sizes:{key: qty}}}}}."""
    out = {}
    for it in order.get("items") or []:
        pid = (it.get("product") or {}).get("id") if isinstance(it.get("product"), dict) else it.get("product")
        if not pid:
            continue
        e = out.setdefault(pid, {"name": it.get("name"), "variants": {}})
        for v in it.get("variants") or []:
            e["variants"][str(v.get("name") or "").strip().lower()] = {"id": v.get("variantId"), "name": v.get("name"), "sizes": {a["key"]: a.get("quantity") for a in v.get("amounts") or []}}
    return out


def _item_for(doc_item, order, products_by_id):
    """PO-Item (Produkt-ID) zu einer Beleg-Position: ueber Stylenummer im Namen/SKU."""
    want = ({core.norm(doc_item.get("sku"))} | core.style_tokens(doc_item.get("name"))) - {""}
    best = None
    for it in order.get("items") or []:
        pid = (it.get("product") or {}).get("id") if isinstance(it.get("product"), dict) else it.get("product")
        if not pid:
            continue
        have = (core.style_tokens(it.get("name")) | {core.norm(products_by_id.get(pid))}) - {""}
        if want & have or any(len(h) >= 5 and (w.startswith(h) or h.startswith(w)) for w in want for h in have):
            best = pid
            break
    return best


def lines_from_doc(doc, order, products_by_id):
    """Beleg-Positionen -> Sendungszeilen [{id: produktId, orderId, variants: [{id, name, sizes: [{size, quantityToShip}]}]}] + Liste nicht zuordenbarer Positionen."""
    lines, unmapped = {}, []
    ol = order_lines(order)
    for it in doc.get("items") or []:
        pid = _item_for(it, order, products_by_id)
        if not pid or pid not in ol:
            unmapped.append(it.get("sku") or it.get("name")); continue
        ent = lines.setdefault(pid, {"id": pid, "orderId": order["id"], "variants": {}})
        for v in it.get("variants") or []:
            col = str(v.get("color") or "").strip().lower()
            cands = list(ol[pid]["variants"].values())
            ov = ol[pid]["variants"].get(col)
            if not ov and col:
                hit = [x for x in cands if color_match(col, x["name"])]
                ov = hit[0] if len(hit) == 1 else None
            if not ov and len(cands) == 1 and (not col or str(cands[0]["name"]).lower() in ("default style", "")):
                ov = cands[0]
            if not ov:
                unmapped.append("%s %s" % (it.get("sku") or it.get("name"), v.get("color"))); continue
            sizes = {k: q for k, q in (v.get("sizes") or {}).items() if q}
            if not sizes and v.get("quantity"):
                sizes = {(next(iter(ov["sizes"])) if len(ov["sizes"]) == 1 else "ONE SIZE"): v["quantity"]}
            if sizes and ov["sizes"]:
                bad = [k for k in sizes if k not in ov["sizes"]]
                if bad and len(ov["sizes"]) == 1:   # PO fuehrt die Zeile nur als eine Groesse (z. B. ONE SIZE): Belegmengen dort zusammenfassen
                    only = next(iter(ov["sizes"])); sizes = {only: sum(sizes.values())}
                elif bad:
                    unmapped.append("%s %s Groessen %s nicht in der Order" % (it.get("sku") or it.get("name"), v.get("color"), ",".join(bad))); continue
            ev = ent["variants"].setdefault(ov["name"], {"id": ov.get("id"), "name": ov["name"], "sizes": {}})
            for k, q in sizes.items():
                ev["sizes"][k] = ev["sizes"].get(k, 0) + q
    out = []
    for ent in lines.values():
        vs = [{**({"id": v["id"]} if v.get("id") else {}), "name": v["name"], "sizes": [{"size": k, "quantityToShip": q} for k, q in v["sizes"].items()]} for v in ent["variants"].values() if v["sizes"]]
        if vs:
            out.append({"id": ent["id"], "orderId": ent["orderId"], "variants": vs})
    return out, unmapped


def full_order_lines(order):
    """Alle Positionen der Order mit ihren Mengen (wenn kein Beleg mit Mengen vorliegt)."""
    out = []
    for pid, e in order_lines(order).items():
        vs = [{**({"id": v["id"]} if v.get("id") else {}), "name": v["name"], "sizes": [{"size": k, "quantityToShip": q} for k, q in v["sizes"].items() if q]} for v in e["variants"].values()]
        vs = [v for v in vs if v["sizes"]]
        if vs:
            out.append({"id": pid, "orderId": order["id"], "variants": vs})
    return out


def shipments_of_order(shipments, order_id):
    return [s for s in shipments if any(p.get("orderId") == order_id for p in s.get("products") or [])]


def has_marker(shipments, marker):
    return any(marker in str(s.get("notes") or "") for s in shipments)


def doc_marker(name, doc):
    return "[doc:%s:%s:%s]" % ((doc.get("source") or {}).get("mail_id") or name, doc.get("po_number"), str(doc.get("doc_type") or "").upper())


def ev_marker(marker):
    return "[ev:%s]" % marker


GENERIC_MARK = ("Mengen = PO-Menge", "Mengen = Order-Menge")   # Sammel-Sendung ueber die ganze Order (Migration bzw. Ereignis ohne Beleg)


def plan_from_docs(deliveries, orders_detail, shipments, products_by_id):
    """deliveries: [(dateiname, beleg, order_id)] (nur Rechnung/Packliste mit eindeutiger Order). -> (create[], human[])."""
    create, human = [], []
    for name, doc, oid in deliveries:
        order = orders_detail.get(oid)
        mk = doc_marker(name, doc)
        if not order:
            human.append((name, "Order-Details nicht lesbar")); continue
        if has_marker(shipments, mk) or any(c["marker"] == mk for c in create):
            continue
        if not doc.get("items"):
            continue
        if is_packaging_doc(doc):
            human.append((name, "Beleg ist eine Verpackungs-/Etikett-Freigabe oder Planung, kein Versandbeleg: keine Sendung")); continue
        generic = [x for x in shipments_of_order(shipments, oid) if any(g in str(x.get("notes") or "") for g in GENERIC_MARK)]
        if generic:   # sonst wuerden Teilmengen zusaetzlich zur Gesamtmenge gezaehlt
            human.append((name, "Order hat schon eine Sammel-Sendung ueber die ganze Menge (%s): Teilsendung ersetzt sie oder ergaenzt sie? Mensch entscheidet" % generic[0].get("title"))); continue
        lines, unmapped = lines_from_doc(doc, order, products_by_id)
        if not lines or unmapped:   # alles oder nichts: eine Sendung mit fehlenden Mengen waere falscher als keine
            human.append((name, "Beleg laesst sich der Order nicht vollstaendig zuordnen (%s%s): keine Sendung angelegt" % (", ".join(str(u) for u in unmapped[:4]), " ..." if len(unmapped) > 4 else ""))); continue
        text = " ".join(str(x) for x in (doc.get("notes"), doc.get("po_number"), " ".join(doc.get("open") or [])))
        method, known = guess_method(text)
        ref_m = method_from_ref(doc.get("po_number"))
        if ref_m:
            method, known = ref_m, True
        suffix = str(doc.get("po_number") or "").strip()
        title = ("Sendung %s %s" % (order["title"], suffix if suffix and core.norm(suffix) not in core.norm(order["title"]) else "")).strip()
        notes = ["%s %s %s Stk" % (str(doc.get("doc_type") or "Beleg"), doc.get("po_number") or "", sum(q["quantityToShip"] for l in lines for v in l["variants"] for q in v["sizes"]))]
        if unmapped:
            notes.append("Nicht zugeordnet: " + ", ".join(str(u) for u in unmapped[:6]))
        if not known:
            notes.append("Methode angenommen (sea), im Beleg nicht belegt")
        notes.append("Mengen laut Beleg (Teilsendung). " + mk)
        create.append({"title": title[:200], "method": method, "status": "pending", "trackingNumber": "", "notes": " | ".join(notes), "products": lines, "marker": mk, "order": order["title"]})
    return create, human


def plan_from_events(order_id, order_title, ship_events, orders_detail, shipments):
    """ship_events: [{marker, milestone, tracking, mode, text}] zu EINER Order (stark belegt). -> (create[], update[], human[])."""
    create, update, human = [], [], []
    mine = shipments_of_order(shipments, order_id)
    order = orders_detail.get(order_id)
    upd_by_id = {}

    def add_update(s, patch, note):
        """Mehrere Ereignisse zur selben Sendung in EINEM Lauf: Notizen und Felder in EINEN PUT zusammenfassen (sonst ueberschreibt der zweite PUT die Notiz des ersten)."""
        u = upd_by_id.get(s["id"])
        if u is None:
            u = {"id": s["id"], "title": s.get("title"), "patch": {}}
            upd_by_id[s["id"]] = u; update.append(u)
        base = u["patch"].get("notes", str(s.get("notes") or ""))
        u["patch"]["notes"] = (base + (" | " if base else "") + note).strip(" |")
        for k, v in patch.items():
            if k == "trackingNumber" and (u["patch"].get(k) or s.get(k)):
                continue
            if k == "status" and RANK.get(u["patch"].get(k), 0) >= RANK[v]:
                continue
            u["patch"][k] = v

    for ev in ship_events:
        mk = ev_marker(ev["marker"])
        if has_marker(mine, mk) or has_marker(shipments, mk) or any(c["marker"] == mk for c in create) or any(mk in u["patch"].get("notes", "") for u in update):
            continue
        target = MILESTONE_STATUS.get(ev.get("milestone"))
        open_ships = [s for s in mine if s.get("status") != "delivered"]
        mode = (ev.get("mode") or "").strip().lower()
        if len(open_ships) > 1 and mode in ("sea", "air", "ground"):   # Ereignis nennt den Transportweg: genau EINE offene Sendung dieser Art ist eindeutig
            same = [s for s in open_ships if s.get("method") == mode]
            if len(same) == 1:
                open_ships = same
        trk = (ev.get("tracking") or "").strip()
        if target:
            if len(open_ships) == 1:
                s = open_ships[0]
                patch = {}
                if RANK[target] > RANK.get(s.get("status"), 0):
                    patch["status"] = target
                if trk and not s.get("trackingNumber"):
                    patch["trackingNumber"] = trk
                add_update(s, patch, "%s %s %s" % (ev.get("milestone"), (ev.get("text") or "")[:160], mk))
            elif not mine and target == "in_transit" and order:
                lines = full_order_lines(order)
                if lines:
                    method, known = guess_method(" ".join([ev.get("mode") or "", ev.get("text") or ""]))
                    create.append({"title": ("Sendung %s" % order_title)[:200], "method": method, "status": "in_transit", "trackingNumber": trk,
                                   "notes": "Verladen laut Mail. Mengen = Order-Menge (Teilsendung moeglich). %s%s" % ("" if known else "Methode angenommen (sea). ", mk), "products": lines, "marker": mk, "order": order_title})
                else:
                    human.append((order_title, "Verladen gemeldet, aber Order ohne Positionen/Mengen"))
            elif len(open_ships) > 1:
                human.append((order_title, "%s gemeldet, aber %d offene Sendungen: Mensch ordnet zu" % (ev.get("milestone"), len(open_ships))))
            elif mine and not open_ships:
                continue   # alle Sendungen der Order sind schon geliefert: nichts zu tun
            else:
                human.append((order_title, "%s gemeldet, keine passende Sendung/Order" % ev.get("milestone")))
        elif trk and len(open_ships) == 1 and not open_ships[0].get("trackingNumber"):
            s = open_ships[0]
            add_update(s, {"trackingNumber": trk}, "Tracking %s %s" % (trk, mk))
    return create, update, human


def apply(create, update, call):
    """Schreibt per REST (call = plm_client.call). Gibt Protokollzeilen zurueck; bricht bei unerwartetem Status ab."""
    log = []
    for c in create:
        body = {k: v for k, v in c.items() if k not in ("marker", "order")}
        st, r = call("POST", "shipments", body)
        log.append("Sendung neu: %s -> HTTP %s" % (c["title"], st))
        if st not in (200, 201):
            raise RuntimeError("POST /shipments HTTP %s: %s" % (st, str(r)[:200]))
    for u in update:
        st, r = call("PUT", "shipments/" + u["id"], u["patch"])
        log.append("Sendung aktualisiert: %s %s -> HTTP %s" % (u.get("title"), list(u["patch"].keys()), st))
        if st not in (200, 201):
            raise RuntimeError("PUT /shipments HTTP %s: %s" % (st, str(r)[:200]))
    return log
