"""Backtest des inhaltsbasierten Matchers (plm_intake.content_match). Nur Lesen.

Wahrheit: Ereignisse, deren Marker (ev:<Hash>) als BELEGT zugeordnete Notizzeile (ohne '[Zuordnung: ...]'-Zusatz) in den Notizen einer Order stehen.
Kennungen (PO-Nr, Container, B/L, Rechnungsnr., Order-Kennungen aus den Notizen) werden im Ereignis ausgeblendet, Notizzeilen derselben Mail aus dem Order-Profil entfernt.
Population = Ereignisse, die danach in events.find_order (ohne Inhalts-Matcher) 'mehrdeutig' bleiben (wie im Echtbetrieb). Kandidaten wie im Betrieb:
laufende Orders des Lieferanten bzw. die im Grund genannten Orders; fehlt die wahre Order dort (z. B. inzwischen Complete), ist jede Zuordnung ein Fehler.

  .venv/bin/python -m plm_intake.content_backtest --ctx ctx.json [--inbox DIR] [--sweep] [--json out.json]
ctx.json: {"vendors","products","orders"} wie plm_intake.context.load_context (+ add_po_numbers fuer _notes/poNumber)."""
import argparse
import copy
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import content_match as cm, core, events  # noqa: E402

LINE = re.compile(r"\[\d{4}-\d{2}-\d{2}[^\]]*?ev:([0-9a-f]{8})\][^\n]*")
CONTAINER = re.compile(r"\b[A-Z]{4}\d{7}\b|\bPO\d{2}-\d+\b", re.I)


def truth_map(orders):
    """marker -> order_id fuer belegte Zeilen (kein '[Zuordnung:'-Zusatz); Marker, die auf mehrere Orders zeigen, entfallen."""
    m = defaultdict(set)
    for o in orders:
        for l in LINE.finditer(str(o.get("_notes") or "")):
            if "[Zuordnung:" not in l.group(0):
                m[l.group(1)].add(o["id"])
    return {k: next(iter(v)) for k, v in m.items() if len(v) == 1}


def mask(e, truth_order, idx):
    """Kopie des Ereignisses ohne Kennungen (explizite Felder und Order-Kennungen aus den Notizen; Styles/SKUs bleiben)."""
    e = copy.deepcopy(e)
    idents = set(idx.get(truth_order["id"], {}).get("idents", set())) | {core.norm(truth_order.get("poNumber"))}
    codes = cm.profile(truth_order, idx)["codes"]
    ref = e.get("ref") or {}
    kill = set()
    for k in ("po_number", "container"):
        if ref.get(k):
            kill.add(core.norm(ref[k])); ref[k] = None
    d = e.get("details") or {}
    for k in events.IDENT_KEYS + ("invoice_no", "containers", "hbl", "mbl"):
        if d.get(k) not in (None, "", False):
            kill |= {core.norm(x) for x in re.split(r"[,;\s]+", str(d[k])) if x}
            d[k] = None
    src = e.get("source")
    if isinstance(src, dict) and src.get("doc"):
        kill.add(core.norm(src["doc"])); src["doc"] = None
    kill.discard("")

    def clean(t):
        if not isinstance(t, str):
            return t
        def rep(m):
            n = core.norm(m.group(0))
            if n in codes:
                return m.group(0)
            return " " if (n in kill or n in idents or any(len(k) >= 5 and k in n for k in kill)) else m.group(0)
        t = CONTAINER.sub(" ", t)
        return re.sub(r"[A-Za-z0-9][A-Za-z0-9._/\-]{4,}", rep, t)

    for k in ("summary", "source_quote", "subject"):
        if e.get(k):
            e[k] = clean(e[k])
    for k, v in list(d.items()):
        d[k] = clean(v)
    m = e.get("_mail") or {}
    if m.get("subject"):
        m["subject"] = clean(m["subject"])
    return e


def population(ctx, evs, vend_al, aliases_po=None, style_aliases=None, mode="mehrdeutig", overrides=None):
    """-> Liste dicts {event(maskiert), truth, cands, why, vendor}"""
    orders = [o for o in ctx["orders"] if not events.TEST_ORDER.search(str(o.get("title") or ""))]
    by_id = {o["id"]: o for o in orders}
    idx = events.order_index(orders, ctx["products"])
    dom = events.domain_vendors(ctx["vendors"])
    tm = truth_map(orders)
    for k, v in (overrides or {}).items():
        if v in by_id and v != events.INFO_OVERRIDE:
            tm.setdefault(k, v)
    out = []
    os.environ.pop("CONTENT_MATCH", None)
    seen = set()
    for e in sorted(evs, key=lambda x: str(x["_mail"].get("date") or "")):
        mk = events.marker(e)
        if mk in seen or mk not in tm or tm[mk] not in by_id:
            continue
        seen.add(mk)
        t = by_id[tm[mk]]
        e2 = mask(e, t, idx)
        o, why = events.find_order(e2, orders, ctx["vendors"], aliases_po, vend_al, True, idx, dom, style_aliases)
        v = events.vendor_of(e2, ctx["vendors"], vend_al, dom)
        if mode == "alle":   # alle Wahrheits-Ereignisse mit bekanntem Lieferanten: nur Kennungen maskiert, vorhandene Regeln ausser Kraft
            if not v:
                continue
            why = "alle"
            cands = [x for x in orders if (x.get("manufacturer") or {}).get("id") == v["id"] and events._status(x) not in events.ACTIVE_NOT]
            if len(cands) >= 2:
                out.append({"event": e2, "marker": mk, "truth": t, "cands": cands, "why": why, "vendor": v["name"], "mail": str((e.get("_mail") or {}).get("id"))})
            continue
        if o or not why.startswith("mehrdeutig:"):
            continue
        if "laufende Orders" in why:
            cands = [x for x in orders if (x.get("manufacturer") or {}).get("id") == (v or {}).get("id") and events._status(x) not in events.ACTIVE_NOT]
        else:
            names = [s.strip() for s in why.split(":", 1)[1].split(",")]
            cands = [x for x in orders if x["title"] in names and events._status(x) not in events.ACTIVE_NOT]
        out.append({"event": e2, "marker": mk, "truth": t, "cands": cands, "why": why, "vendor": (v or {}).get("name") or "?", "mail": str((e.get("_mail") or {}).get("id"))})
    return out, idx


def run(pop, idx):
    rows = []
    for p in pop:
        o, beleg, det = cm.match(p["event"], p["cands"], idx, own_mail=p["mail"])
        in_c = any(c["id"] == p["truth"]["id"] for c in p["cands"])
        rows.append({"vendor": p["vendor"], "marker": p["marker"], "assigned": bool(o), "correct": bool(o) and o["id"] == p["truth"]["id"], "truth_in": in_c,
                     "beleg": beleg, "reason": det.get("reason"), "rank": det.get("ranking"), "truth_title": p["truth"]["title"], "got": o["title"] if o else None,
                     "text": str(p["event"].get("summary"))[:140]})
    return rows


def summarize(rows):
    byv = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        b = byv[r["vendor"]]
        b[0] += 1; b[1] += r["assigned"]; b[2] += r["correct"]
    tot = [len(rows), sum(r["assigned"] for r in rows), sum(r["correct"] for r in rows)]
    return tot, dict(byv)


def fmt(tot, byv):
    prec = (100.0 * tot[2] / tot[1]) if tot[1] else 0.0
    cov = (100.0 * tot[1] / tot[0]) if tot[0] else 0.0
    L = ["Population %d | zugeordnet %d | richtig %d | Praezision %.1f %% | Abdeckung %.1f %%" % (tot[0], tot[1], tot[2], prec, cov)]
    for v, (n, a, c) in sorted(byv.items(), key=lambda x: -x[1][0]):
        L.append("  %-34s n=%3d zugeordnet=%3d richtig=%3d  Praez. %s  Abdeckung %.0f %%" % (v[:34], n, a, c, ("%.0f %%" % (100.0 * c / a)) if a else "-", 100.0 * a / n))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--inbox")
    ap.add_argument("--intake", default=str(ROOT / "output" / "intake"))
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--alle", action="store_true", help="Population = alle Wahrheits-Ereignisse mit bekanntem Lieferanten und >=2 laufenden Orders (statt nur find_order-mehrdeutig)")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    from plm_intake import daily
    ctx = json.load(open(a.ctx))
    inbox = daily.resolve_inbox(a.inbox, Path(a.intake))
    evs = events.load_events(sorted(inbox.glob("*_events.json")))
    intake = Path(a.intake)
    vend_al = json.load(open(intake / "vendor_aliases.json")) if (intake / "vendor_aliases.json").exists() else {}
    po_al = json.load(open(intake / "po_aliases.json")) if (intake / "po_aliases.json").exists() else {}
    st_al = json.load(open(intake / "style_aliases.json")) if (intake / "style_aliases.json").exists() else {}
    ov = json.load(open(intake / "event_overrides.json")) if (intake / "event_overrides.json").exists() else {}
    pop, idx = population(ctx, evs, vend_al, po_al, st_al, "alle" if a.alle else "mehrdeutig", ov)
    print("Wahrheits-Ereignisse in Population (nach find_order mehrdeutig): %d" % len(pop))
    if a.sweep:
        for ms in (4, 5, 6, 7, 8, 9):
            for mg in (2, 3, 4, 5, 6):
                cm.MIN_SCORE, cm.MARGIN = ms, mg
                tot, _ = summarize(run(pop, idx))
                print("MIN_SCORE %d MARGIN %d -> zugeordnet %d richtig %d Praezision %s" % (ms, mg, tot[1], tot[2], ("%.1f %%" % (100.0 * tot[2] / tot[1])) if tot[1] else "-"))
        return 0
    rows = run(pop, idx)
    tot, byv = summarize(rows)
    print("MIN_SCORE %d MARGIN %d" % (cm.MIN_SCORE, cm.MARGIN))
    print(fmt(tot, byv))
    wrong = [r for r in rows if r["assigned"] and not r["correct"]]
    for r in wrong:
        print("FALSCH [%s] wahr=%s (in Kandidaten: %s) bekommen=%s | %s | %s" % (r["vendor"], r["truth_title"], r["truth_in"], r["got"], r["beleg"], r["text"]))
    if a.json:
        json.dump(rows, open(a.json, "w"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
