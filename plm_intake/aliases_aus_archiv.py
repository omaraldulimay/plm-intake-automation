"""Aliase (Kennung -> Order) aus dem lokalen Mail-Archiv ableiten. NUR LOKAL (die Cloud hat weder Mailtexte noch Anhaenge). Schreibt nichts ins PLM.

  python3 -m plm_intake.aliases_aus_archiv                  Trockenlauf (Standard): Vorschlaege + Bericht, schreibt nichts
  python3 -m plm_intake.aliases_aus_archiv --apply          schreibt die eindeutigen Aliase NUR nach output/intake/po_aliases.json (Sicherung output/backup/);
                                                            kein Push in den Zustandszweig: die Aliase gelten in der Cloud erst, wenn die Datei in den Zweig 'einpflege-zustand' uebertragen ist
  Optionen: --ctx ctx.json (statt Live-Abfrage, nur GET) | --state-ref origin/einpflege-zustand ('' = nur lokale Dateien) | --mails DIR | --inbox DIR | --report datei.md

Ziel sind die OFFENEN Ereignisse (events.plan, Klaerfaelle): jede Kennung dieser Ereignisse (Container, B/L, Rechnungsnummer, AWB, Speditions-Akte IM.00xxxx im Betreff) wird im Archiv gesucht.
Eine Kennung wird nur dann Alias, wenn ALLE Quellen, die sie nennen und eine Order erkennen lassen, auf GENAU EINE Order zeigen:
  1) Verlauf: Mails desselben Gmail-Verlaufs nennen im Betreff/Anhangsnamen eine Order-Kennung (poNumber, z. B. 'PO26005SG-W-2 packing list.pdf' -> Lieferant T); der Verlauf zeigt auf genau eine Order
  2) Anhang (xlsx): Rechnung/Packliste nennt Styles, die nur in EINER Order vorkommen (z. B. HY29582+HY29583+HY29587 -> Lieferant W DE-EA-2); die Rechnungsnummer im Blatt wird Alias
  3) Containerliste (xlsx 'Gesamtuebersicht'): Container/Packlisten-Nr mit Lieferant + IAN + EINEM Land, das zu genau einer Order passt (Titel -DE-/-CH-/-LAGER-)
  4) Spediteur-Akte: Mails mit derselben Akte/Container in einem Verlauf, der auf eine Order zeigt (Mail mit Lieferantenname im Betreff und der Lieferant hat nur EINE Order, z. B. 'Lieferant U' -> Lieferant U)
Widerspruch (zwei Orders) = kein Alias. Der Lieferant des Ereignisses muss zur Order passen. Bestehende Aliase werden nie ueberschrieben (alias_learn.merge: Konflikt = mehrdeutig)."""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import alias_learn, core, events  # noqa: E402

DRIVE = Path.home() / "Library/CloudStorage/kontakt@firma.example/Meine Ablage"
MAILS = DRIVE / "PLM-Mails"
INBOX = DRIVE / "Inbox"
INTAKE = ROOT / "output" / "intake"
STATE_REF = "origin/einpflege-zustand"
STATE_NAMES = ["ledger.json", "po_aliases.json", "vendor_aliases.json", "style_aliases.json", "event_overrides.json", "mail_threads.json", "programme.json", "vendor_domains.json"]
ATT_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}_[0-9a-f]{12,}_")
LAND_TITEL = {"DE": "-DE-", "CH": "-CH-", "LAGER": "-LAGER-"}   # Land der Containerliste -> Titelteil der Orders (OSDE o. a.: unbekannt = nicht zuordnen)


def _ident_ok(n):
    return len(n) >= 6 and re.search(r"[a-z]", n) is not None and re.search(r"\d", n) is not None


# ---------------- Archiv lesen ----------------
def parse_block(block):
    head, _, text = block.partition("----- TEXT -----")
    h = {}
    for ln in head.splitlines():
        k, _, v = ln.partition(":")
        if v and k in ("Message-ID", "Thread-ID", "Datum", "Von", "Betreff", "Anhaenge"):
            h[k] = v.strip()
    if not h.get("Message-ID"):
        return None
    att = [ATT_PREFIX.sub("", a.strip()) for a in h.get("Anhaenge", "-").split(" | ") if a.strip() and a.strip() != "-"]
    att_raw = [a.strip() for a in h.get("Anhaenge", "-").split(" | ") if a.strip() and a.strip() != "-"]
    return {"id": h["Message-ID"], "thread": h.get("Thread-ID") or h["Message-ID"], "date": h.get("Datum", ""), "from": h.get("Von", ""), "subject": h.get("Betreff", ""),
            "att": att, "att_raw": att_raw, "text": text[:30000]}


def read_mails(root=MAILS):
    out = []
    root = Path(root)
    for f in sorted(root.glob("mails_*.txt")):
        for b in f.read_text(errors="ignore").split("===== MAIL ====="):
            m = parse_block(b)
            if m:
                out.append(m)
    seen = {m["id"] for m in out}
    for d in root.iterdir():
        mt = d / "mail.txt"
        if d.is_dir() and mt.exists() and d.name.rsplit("_", 1)[-1] not in seen:
            m = parse_block(mt.read_text(errors="ignore"))
            if m:
                out.append(m)
    return out


# ---------------- Order-Kennungen ----------------
def order_ids(orders):
    """{Order-ID: {normierte Kennung >= 6 Zeichen}}: poNumber (+ PO-ID). Nur Kennungen mit Buchstaben UND Ziffern."""
    from plm_intake import po_ids
    out = {}
    for o in orders:
        ids = set()
        for x in (o.get("poNumber"), po_ids.po_id(o) if o.get("createdAt") else None):
            n = core.norm(x)
            if _ident_ok(n):
                ids.add(n)
        out[o["id"]] = ids
    return out


def orders_in(text, ids):
    """Orders, deren Kennung als Teil eines Wortes (Betreff-/Dateiname-Token) in text steht. Je Token zaehlt bei Kennung-in-Kennung (…-2 / …-2EXTRA) nur die laengere, spezifischere;
    steht in einem Text beides (zwei Dateien), sind es beide Orders."""
    out = set()
    for tok in re.findall(r"[^\s|,;()\[\]{}\"']+", str(text or "")):
        tn = core.norm(tok)
        hit = {oid: max((i for i in s if i in tn), key=len, default=None) for oid, s in ids.items()}
        hit = {k: v for k, v in hit.items() if v}
        out |= {a for a in hit if not any(b != a and hit[a] != hit[b] and hit[b].startswith(hit[a]) for b in hit)}
    return out


def thread_orders(mails, ids):
    """{Gmail-Verlauf: {Order-IDs}} aus Betreff und Anhangsnamen aller Mails des Verlaufs (Evidenz 1)."""
    t = defaultdict(set)
    for m in mails:
        t[m["thread"]] |= orders_in(m["subject"] + " " + " ".join(m["att"]), ids)
    return t


# ---------------- xlsx ----------------
def xlsx_cells(path, max_rows=600):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except Exception:
        return []
    rows = []
    for ws in wb.worksheets[:6]:
        try:
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= max_rows:
                    break
                rows.append((ws.title, [("" if c is None else str(c).strip()) for c in row]))
        except Exception:
            continue
    return rows


def sku_index(orders, products):
    """{Order-ID: {norm(SKU)}}."""
    sku = {p["id"]: core.norm(p.get("sku")) for p in products if p.get("sku")}
    return {o["id"]: {sku[i["product"]["id"]] for i in o.get("items") or [] if isinstance(i.get("product"), dict) and i["product"].get("id") in sku} - {""} for o in orders}


def xlsx_invoice_evidence(rows, skus):
    """-> (Rechnungsnummern, {Order-IDs}) : alle Orders, die ALLE im Blatt genannten Styles haben (mind. 2 verschiedene Styles). Als Beleg zaehlt nur genau EINE Order, mehrere = nur Gegenprobe."""
    allsku = set().union(*skus.values()) if skus else set()
    found = set()
    inv = set()
    for _t, row in rows:
        for j, c in enumerate(row):
            n = core.norm(c)
            if n in allsku:
                found.add(n)
            if re.search(r"inv(oice)?\.?\s*(no|nr|#)", c, re.I):
                for x in row[j + 1:j + 3]:
                    if _ident_ok(core.norm(x)):
                        inv.add(x)
                        break
    return inv, {oid for oid, s in skus.items() if len(found) >= 2 and found <= s}


def container_list(rows, orders, vendors, skus):
    """Containerliste (Spalten 'Container No', 'Supplier', 'Article No.', 'Country', 'Packing List / Ref.') -> {norm(Container oder Packlisten-Nr): Order-ID} nur bei EINEM Land und genau einer passenden Order."""
    head = next(((i, r) for i, (_t, r) in enumerate(rows) if "container no" in [x.lower() for x in r]), None)
    if not head:
        return {}
    cols = {x.lower(): j for j, x in enumerate(head[1])}
    need = [cols.get(k) for k in ("container no", "supplier", "article no.", "country", "packing list / ref.")]
    if None in need:
        return {}
    per = defaultdict(lambda: {"v": set(), "ian": set(), "land": set(), "ref": set()})
    for _t, r in rows[head[0] + 1:]:
        if len(r) <= max(need) or not r[need[0]]:
            continue
        d = per[core.norm(r[need[0]])]
        d["v"].add(r[need[1]]); d["ian"].add(core.norm(re.sub(r"\.0$", "", r[need[2]]))); d["land"].add(r[need[3]].upper()); d["ref"].add(r[need[4]])
    out = {}
    byref = defaultdict(set)
    for cn, d in per.items():
        vend = {core.match_vendor(v, vendors)[0] and core.match_vendor(v, vendors)[0]["id"] for v in d["v"]}
        if len(vend) != 1 or None in vend or len(d["land"]) != 1 or next(iter(d["land"])) not in LAND_TITEL:
            continue
        tok = LAND_TITEL[next(iter(d["land"]))]
        cand = [o for o in orders if (o.get("manufacturer") or {}).get("id") in vend and tok in str(o.get("title")) and d["ian"] <= skus.get(o["id"], set())]
        if len(cand) == 1:
            out[cn] = cand[0]["id"]
            for ref in d["ref"]:
                byref[core.norm(ref)].add(cand[0]["id"])
    for ref, s in byref.items():
        if len(s) == 1 and _ident_ok(ref):
            out[ref] = next(iter(s))
    return out


# ---------------- Kennungen der offenen Ereignisse ----------------
IDENT_FIELDS = ("invoice_number", "invoice_no", "invoice", "bl", "awb", "hbl", "mbl", "container", "tracking", "tracking_number")


def event_idents(e):
    """{normierte Kennung: Rohform} der Ereignis-Felder und des Mail-Betreffs (Akte IM.00xxxx, Container)."""
    ref, d = e.get("ref") or {}, e.get("details") or {}
    raw = [ref.get("container")] + [d.get(k) for k in IDENT_FIELDS]
    src = e.get("source")
    if isinstance(src, dict):
        raw.append(src.get("doc"))
    out = {}
    for x in raw:
        for t in re.split(r"[,;]+", str(x or "")):
            t = t.strip()
            if t and _ident_ok(core.norm(t)):
                out.setdefault(core.norm(t), t)
    subj = str((e.get("_mail") or {}).get("subject") or "")
    for t in events.AKTE_RE.findall(subj) + events.CONTAINER_RE.findall(subj.upper()):
        out.setdefault(core.norm(t), t)
    return out


# ---------------- Hauptlogik ----------------
def derive(ctx, mails, open_events, att_dir=None):
    """-> (vorschlaege[{ident, key, order_id, order, belege[], events[]}], verworfen[{ident, grund}])
    Je offenem Ereignis (und seinem Gmail-Verlauf im Archiv) werden die Kennungen des Ereignisses auf Orders abgebildet; alle Quellen muessen dieselbe EINE Order nennen."""
    orders = [o for o in ctx["orders"] if not events.TEST_ORDER.search(str(o.get("title") or ""))]
    by_id = {o["id"]: o for o in orders}
    ids = order_ids(orders)
    skus = sku_index(orders, ctx["products"])
    tord = thread_orders(mails, ids)                       # Evidenz 1
    by_mail = {m["id"]: m for m in mails}
    by_thread = defaultdict(list)
    for m in mails:
        by_thread[m["thread"]].append(m)
    mail_norm = {m["id"]: core.norm(m["subject"] + " " + " ".join(m["att"]) + " " + m["text"][:20000]) for m in mails}
    per_vendor = defaultdict(list)
    for o in orders:
        per_vendor[(o.get("manufacturer") or {}).get("id")].append(o)
    single = {v["id"]: per_vendor[v["id"]][0] for v in ctx["vendors"] if len(per_vendor.get(v["id"], [])) == 1}   # Evidenz 4: Lieferant mit genau EINER Order
    vtoks = {vid: {w for w in core.vendor_tokens(next(v["name"] for v in ctx["vendors"] if v["id"] == vid)) if len(w) >= 5} - core.GENERIC for vid in single}
    xcache = {}

    def xinfo(m):
        """Evidenz 2/3 der Anhaenge EINER Mail: (Rechnungsnummern, Orders per Styles, Containerlisten-Zuordnung). Je Datei nur einmal gelesen."""
        inv_all, cand_all, lst_all = set(), set(), {}
        for raw, name in zip(m["att_raw"], m["att"]):
            f = Path(att_dir) / raw if att_dir else None
            if not f or not name.lower().endswith(".xlsx") or not f.exists():
                continue
            if raw not in xcache:
                rows = xlsx_cells(f, 3000)
                if re.search(r"ges\w*bersicht", name, re.I):
                    xcache[raw] = (set(), set(), container_list([x for x in rows if "bersicht" in x[0] or "ontainer" in x[0]], orders, ctx["vendors"], skus))
                else:
                    i_, c_ = xlsx_invoice_evidence(rows, skus)
                    xcache[raw] = (i_, c_, {})
            i_, c_, l_ = xcache[raw]
            inv_all |= {core.norm(x) for x in i_}; cand_all |= c_; lst_all.update(l_)
        return inv_all, cand_all, lst_all

    def mail_orders(m):
        """Order-IDs, auf die EINE Mail zeigt: Verlauf (Anhangsnamen/Betreff) oder Lieferantenname bei Ein-Order-Lieferant -> (set, Quelle, mehrdeutig)"""
        t = tord.get(m["thread"]) or set()
        if len(t) == 1:
            return t, "Verlauf", False
        if len(t) > 1:
            return set(), "Verlauf mehrdeutig", True
        subj = core.norm(m["subject"])
        v = {vid for vid, w in vtoks.items() if w and any(x in subj for x in w)}
        if len(v) == 1:
            return {single[next(iter(v))]["id"]}, "Lieferantenname im Betreff (Lieferant hat 1 Order)", False
        return set(), "", False

    prop, drop, done = [], [], set()
    for e in open_events:
        v = events.vendor_of(e, ctx["vendors"], ctx.get("aliases"), ctx.get("dom"))
        own = by_mail.get(str((e.get("_mail") or {}).get("id")))
        thread = by_thread.get(own["thread"], []) if own else []
        t_orders = (tord.get(own["thread"]) or set()) if own else set()
        x_inv, x_cand, x_list = set(), set(), {}
        for m in thread:
            i_, c_, l_ = xinfo(m)
            x_inv |= i_; x_cand |= c_; x_list.update(l_)
        for n, rawid in event_idents(e).items():
            if n in done:
                continue
            done.add(n)
            belege, oset, mehr, x_multi = [], set(), False, set()
            if len(t_orders) == 1:
                oset |= t_orders; belege.append("Verlauf des Ereignisses (Anhangsnamen/Betreff)")
            elif len(t_orders) > 1:
                mehr = True
            if n in x_inv and len(x_cand) == 1:
                oset |= x_cand; belege.append("Rechnung/Packliste im Verlauf: Styles nur in dieser Order")
            elif n in x_inv and len(x_cand) > 1:
                x_multi = x_cand
            for m in mails:   # dieselbe Kennung in anderen Mails/Verlaeufen (Akte, Container, Rechnung)
                if m["id"] != (own or {}).get("id") and n in mail_norm[m["id"]]:
                    o_, src, amb = mail_orders(m)
                    if o_:
                        oset |= o_; belege.append("%s: %s" % (m["id"][:8], src))
                    mehr = mehr or amb
            if n in x_list:
                oset.add(x_list[n]); belege.append("Containerliste (Land + IAN)")
            if not oset and not mehr:
                continue
            if x_multi and oset and not oset <= x_multi:   # Rechnung/Packliste passt zu anderen Orders als die Namens-Evidenz: Widerspruch
                drop.append({"ident": rawid, "grund": "Namens-Evidenz (%s) widerspricht den Styles der Rechnung (%s)" % (", ".join(sorted(by_id[x]["title"] for x in oset if x in by_id))[:80], ", ".join(sorted(by_id[x]["title"] for x in x_multi if x in by_id))[:80])})
                continue
            if mehr or len(oset) != 1:
                drop.append({"ident": rawid, "grund": ("mehrere Orders/Verlaeufe: " + ", ".join(sorted(by_id[x]["title"] if x in by_id else x for x in oset))[:160]) if oset else "Verlauf nennt mehrere Orders"})
                continue
            oid = next(iter(oset))
            if v and (by_id[oid].get("manufacturer") or {}).get("id") != v["id"]:
                drop.append({"ident": rawid, "grund": "Lieferant des Ereignisses (%s) passt nicht zur Order %s" % (v["name"], by_id[oid]["title"])}); continue
            prop.append({"ident": rawid, "key": rawid, "order_id": oid, "order": by_id[oid]["title"], "belege": sorted(set(belege))[:6], "events": []})
    pmap = {core.norm(p["ident"]): p for p in prop}
    for e in open_events:
        for n in event_idents(e):
            if n in pmap:
                pmap[n]["events"].append("%s %s: %s" % (events.marker(e), e.get("type"), str(e.get("summary"))[:70]))
    return prop, drop


# ---------------- Zustand / Ereignisse ----------------
def state_from_ref(ref, dest):
    n = 0
    try:
        subprocess.run(["git", "fetch", "-q", "origin", ref.split("/", 1)[-1]], cwd=ROOT, capture_output=True, timeout=60)
    except Exception:
        pass
    for name in STATE_NAMES:
        r = subprocess.run(["git", "show", "%s:intake/%s" % (ref, name)], cwd=ROOT, capture_output=True)
        if r.returncode == 0:
            (Path(dest) / name).write_bytes(r.stdout); n += 1
    return n


def _load(p, default):
    try:
        return json.load(open(p)) if Path(p).exists() else default
    except (OSError, ValueError):
        return default


def open_events(ctx, inbox, st):
    """Offene (nicht zugeordnete, nicht Info) Ereignisse nach dem aktuellen Stand der Zuordnung."""
    evt = events.load_events(sorted(Path(inbox).glob("*_events.json")))
    al = _load(st / "vendor_aliases.json", {})
    ctx["aliases"] = al
    pl = events.plan(evt, ctx["orders"], ctx["vendors"], _load(st / "po_aliases.json", {}), al, vendor_only=True, products=ctx["products"], style_aliases=_load(st / "style_aliases.json", {}),
                     event_overrides=events.load_event_overrides(st), thread_orders=events.load_thread_orders(st), programme_cfg=events.load_programme(st))
    ctx["dom"] = events.domain_vendors(ctx["vendors"])
    return [u["event"] for u in pl["unmatched"] if not str(u["reason"]).startswith("info:") and u["event"].get("type") in events.ORDER_TYPES]


def report(prop, drop, apply, n_events):
    L = ["# Aliase aus dem Mail-Archiv (%s)" % ("geschrieben nach output/intake/po_aliases.json" if apply else "Trockenlauf, nichts geschrieben"), "",
         "Offene Ereignisse betrachtet: %d | eindeutige Aliase: %d | verworfen (mehrdeutig/Lieferant passt nicht): %d" % (n_events, len(prop), len(drop)), ""]
    L += ["## Vorschlaege", ""] + (["- `%s` -> %s | Belege: %s | loest: %s" % (p["key"], p["order"], "; ".join(p["belege"]), " / ".join(p["events"][:3]) or "-") for p in prop] or ["- keine"])
    L += ["", "## Verworfen", ""] + (["- `%s`: %s" % (d["ident"], d["grund"]) for d in drop] or ["- keine"])
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Aliase lokal nach output/intake/po_aliases.json schreiben (Standard: Trockenlauf)")
    ap.add_argument("--ctx", help="Kontext-JSON statt Live-Abfrage")
    ap.add_argument("--state-ref", default=STATE_REF, help="Git-Ref mit dem Zustand der Cloud-Laeufe ('' = nur lokale Dateien)")
    ap.add_argument("--mails", default=str(MAILS)); ap.add_argument("--inbox", default=str(INBOX))
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    tmp = Path(tempfile.mkdtemp(prefix="aliases_archiv_"))
    st = INTAKE
    if a.state_ref:
        (tmp / "state").mkdir()
        if state_from_ref(a.state_ref, tmp / "state") >= 4:
            st = tmp / "state"
        else:
            print("Zustand aus %s nicht lesbar: nehme lokales %s" % (a.state_ref, INTAKE))
    if a.ctx:
        ctx = json.load(open(a.ctx))
    else:
        from plm_intake.context import add_po_numbers, load_context
        ctx = load_context(); add_po_numbers(ctx)
    oe = open_events(ctx, a.inbox, st)
    mails = read_mails(a.mails)
    print("Mails im Archiv: %d | offene Ereignisse: %d" % (len(mails), len(oe)))
    prop, drop = derive(ctx, mails, oe, Path(a.mails) / "Anhaenge")
    rep = report(prop, drop, a.apply, len(oe))
    if a.report:
        Path(a.report).write_text(rep)
    print(rep)
    if not a.apply or not prop:
        return 0
    orders = ctx["orders"]
    base = _load(st / "po_aliases.json", {})
    local = _load(INTAKE / "po_aliases.json", {})
    work = {**local, **base} if st != INTAKE else dict(local)   # Zweig-Stand gewinnt, lokale Zusatz-Eintraege bleiben
    pairs = [(p["key"], p["order_id"], "Archiv") for p in prop]
    merged, new, conf = alias_learn.merge(work, pairs, orders, apply=False)
    bak = ROOT / "output" / "backup" / ("po_aliases_vor_archiv_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    bak.parent.mkdir(parents=True, exist_ok=True); bak.write_text(json.dumps(local, ensure_ascii=False, indent=2, sort_keys=True))
    INTAKE.mkdir(parents=True, exist_ok=True)
    (INTAKE / "po_aliases.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True))
    print("geschrieben: %s (neu %d, Konflikte %d) | Sicherung: %s | NICHT in den Zustandszweig uebertragen" % (INTAKE / "po_aliases.json", len(new), len(conf), bak))
    return 0


if __name__ == "__main__":
    sys.exit(main())
