"""Klaerbogen: alle offenen, nicht zugeordneten Ereignisse (und Belege) je Lieferant, mit zwei Kandidaten-Bestellungen und belegter Begruendung.
Read-only (nur GET auf das PLM, schreibt nur nach output/phase2/B20/). Omar traegt je Fall a / b / info (bzw. skip/create bei Belegen) in die Spalte "Wahl" ein;
plm_intake.klaerbogen_apply schreibt die Wahlen als event_overrides (Marker -> Order-ID, "__info__") und lernt eindeutige Kennungen als Alias.

  python3 -m plm_intake.klaerbogen [--state-ref origin/einpflege-zustand] [--ctx ctx.json] [--inbox DIR] [--out DIR]

Signale (nur belegte, kein Raten): Kennung (Container/B-L/Rechnung) in den Notizen der Order, Smilodox-/Lieferanten-Nummer im Betreff, Stylecode in den Positionen,
Mail-Verlauf (gleicher Betreff wie ein belegtes Ereignis), unterscheidende Woerter (Titel/Position/Variante), genannte Stueckzahl (+-1,5 %).
Konfidenz: hoch = ein starkes Signal mit klarem Abstand, mittel = klarer Vorsprung, niedrig = Signale ohne klaren Vorsprung, keine = nichts spricht (keine Empfehlung).
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import alias_learn, core, events  # noqa: E402

INTAKE = ROOT / "output" / "intake"
OUT = ROOT / "output" / "phase2" / "B20"
STATE_REF = "origin/einpflege-zustand"
STATE_NAMES = ["auto_report.md", "ledger.json", "po_aliases.json", "vendor_aliases.json", "style_aliases.json", "overrides.json", "event_overrides.json", "lieferanten_ids.json"]
W = {"ident": 5, "betreff": 4, "style": 4, "thread_stark": 4, "titel": 3, "menge": 3, "wort": 2, "thread_schwach": 2, "menge_ca": 2}
STOP_WORDS = {"jacket", "pants", "pant", "shirt", "shirts", "hoodie", "black", "white", "olive", "shorts", "socks", "order", "sample", "samples", "women", "woman", "mens", "kids"}
KONF = ("hoch", "mittel", "niedrig", "keine")


def _fmt_n(n):
    return "{:,}".format(int(n)).replace(",", ".")


def short(t, n=150):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    for pat in core.BANK_PATTERNS:
        t = re.sub(pat, "[Bankdaten entfernt]", t)
    return t if len(t) <= n else t[:n - 1] + "…"


# ---------------- Zustand / Kontext ----------------
def state_from_ref(ref, dest):
    """Zustandsdateien aus dem Git-Zweig (neuester Stand der Cloud-Laeufe) nach dest/ kopieren. Rueckgabe: Anzahl."""
    n = 0
    try:
        subprocess.run(["git", "fetch", "-q", "origin", ref.split("/", 1)[-1]], cwd=ROOT, capture_output=True, timeout=60)
    except Exception:
        pass
    for name in STATE_NAMES:
        r = subprocess.run(["git", "show", "%s:intake/%s" % (ref, name)], cwd=ROOT, capture_output=True)
        if r.returncode == 0:
            (Path(dest) / name).write_bytes(r.stdout)
            n += 1
    return n


def _load(p, default):
    try:
        return json.load(open(p)) if Path(p).exists() else default
    except (OSError, ValueError):
        return default


def collect(intake, inbox, ctx, tmp):
    """Wie auto_run (5): Ereignisse + Beleg-Ereignisse in EINEM Plan. Schreibt nichts ins PLM und nichts nach intake (doc_events in tmp)."""
    from plm_intake import daily, docs_existing, ledger
    intake = Path(intake)
    led = ledger.load(intake / "ledger.json")
    docs, evs = daily.pending(inbox, led)
    ctx["aliases"] = _load(intake / "vendor_aliases.json", {})
    po_aliases = _load(intake / "po_aliases.json", {})
    overrides = _load(intake / "overrides.json", {})
    style_aliases = _load(intake / "style_aliases.json", {})
    rows, _ = docs_existing.run(inbox, ctx, overrides, tmp, only={f.name for f in docs})
    by_id = {o["id"]: o["title"] for o in ctx["orders"]}
    for r in rows:
        if r.get("pid") and r.get("po") and r["pid"] in by_id:
            po_aliases.setdefault(str(r["po"]), by_id[r["pid"]])
    evt = events.load_events(evs) + events.load_events(sorted((Path(tmp) / "doc_events").glob("*_events.json")))
    pl = events.plan(evt, ctx["orders"], ctx["vendors"], po_aliases, ctx["aliases"], vendor_only=True, products=ctx["products"], style_aliases=style_aliases,
                     event_overrides=events.load_event_overrides(intake), thread_orders=events.load_thread_orders(intake))
    return {"plan": pl, "events": evt, "rows": rows, "docs": docs, "inbox": Path(inbox), "style_aliases": style_aliases}


# ---------------- Kandidaten ----------------
def order_vendor_id(o):
    m = o.get("manufacturer")
    return m.get("id") if isinstance(m, dict) else m


def _words(text):
    return set(re.findall(r"[a-z]{5,}", str(text or "").lower())) - STOP_WORDS


def order_words(o):
    w = set()
    for it in o.get("items") or []:
        w |= _words(it.get("name"))
        for v in it.get("variants") or []:
            w |= _words(v.get("name")) | _words(v.get("color"))
    return w


def pool_for(vendor, orders):
    live = [o for o in orders if events._status(o) not in events.ACTIVE_NOT]
    return [o for o in live if vendor and order_vendor_id(o) == vendor["id"]] if vendor else live


def pool_from_reason(why, vendor, orders):
    """Nennt der Grund konkrete Orders ('mehrdeutig: A, B'), sind nur diese Kandidaten; sonst laufende Orders des Lieferanten (ohne Lieferant: alle laufenden, dann nur starke Signale)."""
    if str(why).startswith("mehrdeutig:") and "laufende Orders" not in str(why):
        names = [t.strip() for t in str(why).split(":", 1)[1].split(",")]
        named = [o for o in orders if o["title"] in names]
        if named:
            return named, True
    return pool_for(vendor, orders), False


def score_event(group, pool, idx, thread_map, vendor_name, amap, strong_only=False):
    """group: Ereignisse eines Falls (gleiche Mail). -> {order_id: (score, [Begruendung])} nur fuer Orders mit mindestens einem Signal."""
    res = {}
    wordsets = {o["id"]: order_words(o) for o in pool}
    tfreq = {}
    for o in pool:
        for w in events.title_words(o, vendor_name):
            tfreq[w] = tfreq.get(w, 0) + 1

    def add(o, kind, text):
        if strong_only and kind not in ("ident", "betreff", "style", "thread_stark", "titel", "menge"):   # ohne Lieferant: nur Signale, die nicht an Allerweltswoertern haengen
            return
        s = res.setdefault(o["id"], {"score": 0, "kinds": set(), "why": []})
        if kind in s["kinds"]:
            return
        s["kinds"].add(kind); s["score"] += W[kind]; s["why"].append(text)

    for e in group:
        text = " ".join([str(e.get("summary") or ""), str(e.get("source_quote") or "")])
        subj = str((e.get("_mail") or {}).get("subject") or "")
        toks = events.event_tokens(e)
        tcs = events.text_codes(e, amap)
        qx = events.exact_pieces(e)
        qs = events.mentioned_pieces(e)
        tl = text.lower()
        for o in pool:
            ix = idx.get(o["id"], {})
            hit = toks & ix.get("idents", set())
            if hit:
                add(o, "ident", "Kennung %s steht in den Notizen der Order" % sorted(hit)[0].upper())
            sk = ix.get("skus", set())
            names = [core.norm(i.get("name")) for i in o.get("items") or []]
            sh = [t for t in tcs if t in sk or (len(t) >= 6 and any(t in n for n in names))]
            if sh:
                add(o, "style", "Style %s in den Positionen" % sh[0].upper())
            ns = core.norm(subj)
            for key in (core.norm(o.get("poNumber")), core.norm(ix_po_id(o))):
                if key and len(key) >= 6 and key in ns:
                    add(o, "betreff", "Nummer %s im Mail-Betreff" % key.upper()); break
            tw = [w for w in events.title_words(o, vendor_name) if re.search(r"\b%s\b" % re.escape(w), tl + " " + subj.lower())]
            if tw and not (strong_only and tfreq.get(tw[0], 0) > 2):   # ohne Lieferant zaehlt ein Titelwort nur, wenn es hoechstens 2 Orders unterscheidet
                add(o, "titel", "Titelwort '%s' im Text/Betreff" % tw[0])
            tot = float(o.get("totalNumberOfPieces") or 0)
            if qx and tot and abs(qx - tot) <= 0.015 * qx:
                add(o, "menge", "Menge %s = Order %s Stk" % (_fmt_n(qx), _fmt_n(tot)))
            elif tot and not qx:
                m = next((q for q in qs if abs(q - tot) <= 0.015 * q), None)
                if m:
                    add(o, "menge_ca", "genannte Menge ca. %s passt zu %s Stk" % (_fmt_n(m), _fmt_n(tot)))
            others = set().union(*[wordsets[p["id"]] for p in pool if p["id"] != o["id"]]) if len(pool) > 1 else set()
            uw = [w for w in wordsets[o["id"]] - others if re.search(r"\b%s\b" % re.escape(w), tl + " " + subj.lower())]
            if uw and len(pool) > 1:
                add(o, "wort", "Text nennt '%s' (nur in dieser Order, Position/Variante)" % uw[0])
        tk = events.thread_key(e)
        for oid, (n, strong) in (thread_map.get(tk) or {}).items() if tk else []:
            o = next((p for p in pool if p["id"] == oid), None)
            if o:
                add(o, "thread_stark" if strong else "thread_schwach", "Mail-Verlauf: %d belegte%s Ereignis(se) gleicher Betreff -> diese Order" % (n, "" if strong else " (nur schwach)"))
    return res


def ix_po_id(o):
    from plm_intake import po_ids
    return po_ids.po_id(o) or ""


def rank(res, pool):
    """-> (Liste [(order, score, why)] absteigend, Konfidenz)."""
    by_id = {o["id"]: o for o in pool}
    lst = sorted(((by_id[i], v["score"], v["why"], v["kinds"]) for i, v in res.items() if i in by_id), key=lambda x: -x[1])
    if not lst:
        return [], "keine"
    top = lst[0][1]
    second = lst[1][1] if len(lst) > 1 else 0
    strong = bool(lst[0][3] & {"ident", "betreff", "style", "thread_stark"})
    if strong and top >= 4 and top - second >= 3:
        return lst, "hoch"
    if top >= 2 and top - second >= 1:
        return lst, "mittel"
    return lst, "niedrig"


def thread_map_of(pl):
    """thread_key -> {order_id: (Anzahl belegter Ereignisse, stark?)} aus den eigenen Treffern des Plans."""
    m = {}
    for e, oid, why in pl.get("assigned") or []:
        tk = events.thread_key(e)
        if not tk:
            continue
        n, st = m.setdefault(tk, {}).get(oid, (0, False))
        m[tk][oid] = (n + 1, st or why not in events.WEAK)
    return m


def order_label(o):
    return {"id": o["id"], "title": o["title"], "nr": o.get("orderNumber"), "po_id": ix_po_id(o), "status": events._status(o), "pieces": o.get("totalNumberOfPieces")}


# ---------------- Belege ----------------
def doc_candidates(row, doc, pool):
    """Kandidaten fuer einen Beleg, der zu mehreren Orders passt: Stueckzahl, Styles. -> (ranked, Konfidenz)."""
    res = {}
    pcs = None
    try:
        pcs = float(doc.get("total_pieces") or 0)
    except (TypeError, ValueError):
        pass
    names_doc = " ".join(str(i.get("sku") or "") + " " + str(i.get("name") or "") for i in doc.get("items") or [])
    toks = {core.norm(t) for t in events.STYLE_TOKEN.findall(names_doc) if len(core.norm(t)) >= 5}
    for o in pool:
        s = {"score": 0, "kinds": set(), "why": []}
        tot = float(o.get("totalNumberOfPieces") or 0)
        if pcs and tot and abs(pcs - tot) <= 0.015 * pcs:
            s["score"] += W["menge"]; s["kinds"].add("menge"); s["why"].append("Belegmenge %s = Order %s Stk" % (_fmt_n(pcs), _fmt_n(tot)))
        names = [core.norm(i.get("name")) for i in o.get("items") or []]
        sk = [t for t in toks if any(t in n for n in names)]
        if sk:
            s["score"] += W["style"]; s["kinds"].add("style"); s["why"].append("Style %s in den Positionen" % sk[0].upper())
        if s["score"]:
            res[o["id"]] = s
    return rank(res, pool)


def _valid_shape(o, skus):
    """Minimale Order-Form fuer alias_learn.valid (Titel, PO-Nr, Positionsnamen, SKUs), damit das Einlese-Skript ohne PLM-Zugriff Aliase pruefen kann."""
    its = []
    for it in o.get("items") or []:
        p = it.get("product") if isinstance(it.get("product"), dict) else {}
        its.append({"name": str(it.get("name") or "")[:120], "product": {"sku": skus.get(p.get("id"))}})
    return {"id": o["id"], "title": o["title"], "poNumber": o.get("poNumber") or "", "items": its}


def _gleich(ranked):
    """Weitere Orders mit gleichem Punktestand wie Platz 2 (max. 4 genannt)."""
    g = [order_label(r[0])["po_id"] or r[0]["title"] for r in ranked[2:] if r[1] == ranked[1][1] and r[1] > 0] if len(ranked) > 2 else []
    return g[:4] + (["+%d weitere" % (len(g) - 4)] if len(g) > 4 else [])


# ---------------- Aufbau ----------------
def build(col, ctx, intake):
    pl, evt = col["plan"], col["events"]
    orders = [o for o in ctx["orders"] if not events.TEST_ORDER.search(str(o.get("title") or ""))]
    by_id = {o["id"]: o for o in orders}
    idx = events.order_index(orders, ctx["products"])
    amap = events.style_alias_map(col["style_aliases"])
    skus = {p["id"]: p.get("sku") for p in ctx["products"] if p.get("sku")}
    dom = events.domain_vendors(ctx["vendors"])
    tmap = thread_map_of(pl)
    human = [u for u in pl["unmatched"] if not str(u["reason"]).startswith("info:")]
    # je Mail und Lieferant gruppieren
    groups = {}
    for u in human:
        e = u["event"]
        v = events.vendor_of(e, ctx["vendors"], ctx["aliases"], dom)
        k = ((v or {}).get("id") or "", str((e.get("_mail") or {}).get("id")))
        groups.setdefault(k, {"vendor": v, "events": [], "reasons": []})
        groups[k]["events"].append(e); groups[k]["reasons"].append(u["reason"])
    cases = []
    for (vid, mid), g in groups.items():
        v = g["vendor"]
        # Kandidaten je Ereignis, dann Fall = Ereignisse mit gleichem Kandidatensatz
        sub = {}
        for e, why in zip(g["events"], g["reasons"]):
            pool, named = pool_from_reason(why, v, orders)
            ranked, konf = rank(score_event([e], pool, idx, tmap, (v or {}).get("name", ""), amap, strong_only=not v), pool)
            if not ranked and (v or named) and pool and len(pool) <= 2:   # nichts spricht, aber nur 1-2 moegliche Orders: als Auswahl anbieten, ohne Empfehlung
                ranked = [(o, 0, [], set()) for o in pool]
            moegl = [order_label(o)["po_id"] or o["title"] for o in pool] if (v or named) and 2 < len(pool) <= 6 else []
            key = tuple(r[0]["id"] for r in ranked[:2])
            sub.setdefault((key, konf, tuple(moegl)), {"ranked": ranked, "konf": konf, "events": [], "why": [], "moegl": moegl})
            sub[(key, konf, tuple(moegl))]["events"].append(e); sub[(key, konf, tuple(moegl))]["why"].append(why)
        for (key, konf, _m), s in sub.items():
            es = sorted(s["events"], key=lambda x: str((x.get("_mail") or {}).get("date")))
            m = es[0].get("_mail") or {}
            cands = [{"key": "ab"[i], "order": order_label(r[0]), "score": r[1], "begruendung": r[2]} for i, r in enumerate(s["ranked"][:2])]
            gleich = _gleich(s["ranked"])
            cases.append({"gleichauf": gleich, "moegliche": s["moegl"] if not cands or all(c["score"] == 0 for c in cands) else [],
                "art": "ereignis", "vendor": (v or {}).get("name") or "Ohne erkannten Lieferanten", "vendor_id": vid, "konfidenz": konf,
                "mail_id": mid, "betreff_key": events.thread_key({"_mail": m}) or "", "datum": str(m.get("date") or "")[:10], "betreff": short(m.get("subject"), 90),
                "typen": sorted({str(e.get("type")) for e in es}), "grund": short(s["why"][0], 90),
                "ereignisse": [{"marker": events.marker(e), "typ": e.get("type"), "text": short(e.get("summary"), 400), "datum": str(e["_mail"].get("date") or "")[:16],
                                "idents": alias_learn.event_idents(e)} for e in es],
                "kandidaten": cands,
            })
    # Belege
    for r in col["rows"]:
        k = r["kind"]
        if k not in ("AMBIGUOUS_DOC", "ORPHAN_DOC", "BLOCKER"):
            continue
        try:
            doc = json.load(open(col["inbox"] / r["file"]))
        except (OSError, ValueError):
            doc = {}
        src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
        vendor, _ = core.match_vendor(doc.get("vendor") or "", ctx["vendors"], ctx["aliases"]) if doc.get("vendor") else (None, None)
        cands, konf, moegl, gleich = [], "keine", [], []
        if k == "AMBIGUOUS_DOC":
            titles = [t.strip() for t in r["why"].split(":", 1)[1].split(",")]
            pool = [o for o in orders if o["title"] in titles]
            ranked, konf = doc_candidates(r, doc, pool)
            if not ranked and len(pool) <= 2:
                ranked = [(o, 0, [], set()) for o in pool]
            cands = [{"key": "ab"[i], "order": order_label(x[0]), "score": x[1], "begruendung": x[2]} for i, x in enumerate(ranked[:2])]
            moegl = [order_label(o)["po_id"] or o["title"] for o in pool] if not ranked and 2 < len(pool) <= 6 else []
            gleich = _gleich(ranked)
        cases.append({"art": "beleg", "vendor": (vendor or {}).get("name") or str(doc.get("vendor") or "Ohne erkannten Lieferanten"), "vendor_id": (vendor or {}).get("id") or "",
                      "konfidenz": konf, "datei": r["file"], "datum": str(src.get("mail_date") or "")[:10], "betreff": short(src.get("doc"), 90), "kind": k,
                      "beleg": "%s %s, %s Stk" % (doc.get("doc_type"), doc.get("po_number") or doc.get("invoice_number") or "-", doc.get("total_pieces") or "?"),
                      "grund": short(r.get("why") or ("Bestell-PO fehlt im PLM" if k == "ORPHAN_DOC" else ""), 140),
                      "keys": [str(x) for x in (doc.get("po_number"), doc.get("invoice_number"), src.get("doc")) if x not in (None, "", "None")],
                      "kandidaten": cands, "gleichauf": gleich, "moegliche": moegl})
    cases.sort(key=lambda c: (c["art"] == "beleg", c["vendor"].lower(), c.get("betreff_key") or c["betreff"].lower()[:40], c["datum"], c.get("mail_id") or c.get("datei")))
    n_e = n_b = 0
    for c in cases:
        if c["art"] == "ereignis":
            n_e += 1; c["nr"] = "F%02d" % n_e
        else:
            n_b += 1; c["nr"] = "B%02d" % n_b
    gen = hashlib.sha1(json.dumps([[c["nr"], [x["marker"] for x in c.get("ereignisse", [])], c.get("datei"), [k["order"]["id"] for k in c["kandidaten"]]] for c in cases], sort_keys=True).encode()).hexdigest()[:10]
    sendungen = list(col.get("sendungen_human") or [])
    return {"gen_id": gen, "erzeugt": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "faelle": cases, "sendungen": sendungen,
            "orders": {o["id"]: dict(order_label(o), valid=_valid_shape(o, skus)) for o in orders}, "vendors": {v["id"]: v["name"] for v in ctx["vendors"]}}


# ---------------- Ausgabe ----------------
def cell(t):
    return str(t or "").replace("|", "¦").replace("\n", " ")


def cand_cell(c, key):
    k = next((x for x in c["kandidaten"] if x["key"] == key), None)
    if not k:
        if key == "a" and c.get("moegliche"):
            return "keine Empfehlung; moeglich: " + ", ".join(c["moegliche"])
        return "-"
    o = k["order"]
    why = "; ".join(k["begruendung"]) or "kein Signal, nur laufende Order des Lieferanten"
    extra = " (gleichauf: %s)" % ", ".join(c["gleichauf"]) if key == "b" and c.get("gleichauf") else ""
    return "**%s** %s #%s %s - %s%s" % (key, o["po_id"] or "", o["nr"], o["title"], why, extra)


def render_md(b):
    cs = b["faelle"]
    cnt = {k: sum(1 for c in cs if c["konfidenz"] == k) for k in KONF}
    L = ["# Klaerbogen (Stand %s)" % b["erzeugt"], "", "<!-- klaerbogen:%s -->" % b["gen_id"], "",
         "Faelle: %d Ereignis-Faelle (%d Ereignisse), %d Belege. Konfidenz: hoch %d, mittel %d, niedrig %d, keine Empfehlung %d." % (
             sum(1 for c in cs if c["art"] == "ereignis"), sum(len(c.get("ereignisse", [])) for c in cs), sum(1 for c in cs if c["art"] == "beleg"), *[cnt[k] for k in KONF]),
         "", "**So geht's:** je Fall in der letzten Spalte *Wahl* eintragen: `a` oder `b` (Kandidat), `info` (kein Bestellbezug: Spedition/Zoll/Muster/Entwicklung/nicht im PLM), "
         "oder direkt eine Bestellung (PO-ID wie `PO26-036`, Titel oder `#38`). Leer = offen lassen. Bei Belegen: `a`/`b` oder `skip` (ignorieren) / `create` (neue PO). "
         "Ein Fall mit mehreren Ereignissen (gleiche Mail) gilt fuer alle. Danach `python3 -m plm_intake.klaerbogen_apply` (Trockenlauf) und mit `--apply` schreiben.", ""]
    cur = None
    for c in cs:
        head = (c["art"] == "beleg", c["vendor"])
        if head != cur:
            cur = head
            n = sum(1 for x in cs if (x["art"] == "beleg", x["vendor"]) == head)
            L += ["", "## %s%s (%d)" % ("Belege: " if c["art"] == "beleg" else "", c["vendor"], n), "",
                  "| Nr | Datum | Art | Fall | Mail-Betreff / Beleg | Konf. | a | b | Wahl |", "|---|---|---|---|---|---|---|---|---|"]
        if c["art"] == "ereignis":
            ev = c["ereignisse"]
            txt = ev[0]["text"][:160] + (" (+%d weitere aus dieser Mail)" % (len(ev) - 1) if len(ev) > 1 else "")
            art = "/".join(c["typen"])
            subj = c["betreff"]
        else:
            txt = c["beleg"] + (" - " + c["grund"] if c["grund"] else "")
            art = "Beleg " + c["kind"].replace("_DOC", "").lower()
            subj = c["betreff"] + " (" + c["datei"] + ")"
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | |" % (c["nr"], c["datum"], cell(art), cell(txt), cell(subj), c["konfidenz"], cell(cand_cell(c, "a")), cell(cand_cell(c, "b"))))
    if b["sendungen"]:
        L += ["", "## Hinweise (keine Wahl moeglich)"] + ["- " + s for s in b["sendungen"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state-ref", default=STATE_REF, help="Git-Ref mit dem Zustand der Cloud-Laeufe (Standard %s); '' = lokales output/intake" % STATE_REF)
    ap.add_argument("--intake", default=str(INTAKE))
    ap.add_argument("--inbox")
    ap.add_argument("--ctx", help="Kontext-JSON statt Live-Abfrage (nur GET)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--no-browser", action="store_true", help="PO-Nummern/Notizen nicht per Browser nachladen")
    a = ap.parse_args(argv)
    tmp = Path(tempfile.mkdtemp(prefix="klaerbogen_"))
    intake = Path(a.intake)
    if a.state_ref:
        st = tmp / "state"; st.mkdir()
        n = state_from_ref(a.state_ref, st)
        if n < 4:
            print("Zustand aus %s nicht lesbar (%d Dateien): nehme lokales %s" % (a.state_ref, n, intake))
        else:
            intake = st
            print("Zustand aus %s: %d Dateien" % (a.state_ref, n))
    from plm_intake import daily
    inbox = daily.resolve_inbox(a.inbox, INTAKE)
    if not inbox.exists():
        print("Inbox nicht gefunden:", inbox); return 2
    if a.ctx:
        ctx = json.load(open(a.ctx))
    else:
        from plm_intake.context import add_po_numbers, load_context
        ctx = load_context()
        if not a.no_browser:
            print("PO-Nummern/Notizen nachgeladen: %d" % add_po_numbers(ctx))
    col = collect(intake, inbox, ctx, tmp)
    rep = Path(intake) / "auto_report.md"   # Sendungs-Faelle ('Mensch entscheidet') stammen aus dem Lauf, sind hier nur Hinweis (keine Wahl moeglich)
    col["sendungen_human"] = [l[2:].strip() for l in rep.read_text().splitlines() if l.startswith("- Sendung:")] if rep.exists() else []
    b = build(col, ctx, intake)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "klaerbogen.json").write_text(json.dumps(b, ensure_ascii=False, indent=1))
    (out / "klaerbogen.md").write_text(render_md(b))
    cnt = {k: sum(1 for c in b["faelle"] if c["konfidenz"] == k) for k in KONF}
    print("Klaerbogen: %s | Faelle %d (Ereignisse %d, Belege %d) | %s" % (out / "klaerbogen.md", len(b["faelle"]), sum(len(c.get("ereignisse", [])) for c in b["faelle"]),
                                                                          sum(1 for c in b["faelle"] if c["art"] == "beleg"), ", ".join("%s %d" % (k, cnt[k]) for k in KONF)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
