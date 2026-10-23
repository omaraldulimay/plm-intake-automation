"""Preis-Nachtrag: Bestellungen werden auch ohne Stueckpreis angelegt (Preis 0, Notiz 'PREIS AUSSTEHEND'). Kommt spaeter ein Beleg (Proforma/Rechnung/PO) mit
Stueckpreisen zu dieser Order, traegt dieses Modul den Preis je Position nach (Summe wird neu gerechnet).

Regeln: nur Positionen, deren Preis ueberall 0 ist; Style UND Variante (Farbe) UND Menge (+-1,5 %) muessen zur bestehenden Position passen, sonst Klaerfall
'Preis-Nachtrag passt nicht'. Vorhandene Preise > 0 werden NIE ueberschrieben (weicht der Beleg ab -> Hinweis 'UNSTIMMIG', keine Aenderung).
plan() ist eine reine Funktion (testbar, kein PLM-Zugriff). Die Ausfuehrung macht price_fill_template.js im Browser (Trockenlauf = Standard, schreibt nur mit dry=False,
das setzt auto_run bei --apply) mit Vorher/Nachher-Vergleich; es aendert nur Stueckpreis, Kosten, Gesamtsumme und haengt eine Notizzeile an.
  python3 -m plm_intake.price_fill [--ctx snapshot.json] [--inbox DIR]   -> druckt den Plan (Trockenlauf, schreibt nichts)
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402

QTY_TOL = 0.015
PRICE_TOL = 0.01
WHY = "Preis-Nachtrag passt nicht"


def _r2(x):
    return round(float(x) + 1e-9, 2)


def doc_positions(po):
    """[(wanted-Styles, Farbe, Menge, Preis, Anzeige)] je Variante eines Belegs (Preis aus Variante, sonst Position)."""
    out = []
    for it in po.get("items") or []:
        wanted = {core.norm(it.get("sku"))} | core.style_tokens(it.get("name"))
        wanted.discard("")
        variants = it.get("variants") or []
        for v in variants:
            try:
                price = float(v.get("price") if v.get("price") is not None else (it.get("price") or 0))
            except (TypeError, ValueError):
                price = 0.0
            sizes = v.get("sizes") or {}
            try:
                qty = sum(float(q) for q in sizes.values() if q) if sizes else float(v.get("quantity") or 0)
            except (TypeError, ValueError):
                qty = 0.0
            out.append((wanted, v.get("color"), qty, price, "%s %s" % (it.get("sku") or it.get("name"), v.get("color") or "")))
    return out


def _order_qty(v):
    return sum(float(a.get("quantity") or 0) for a in v.get("amounts") or [])


def _is_zero(v):
    return bool(v.get("amounts")) and all(not (a.get("price") or 0) for a in v["amounts"])


def _same_color(dcolor, ovname, single):
    dn, on = core.norm_color(dcolor), core.norm_color(ovname)
    if dn in ("", "default style") or on in ("", "default style"):
        return single
    return dn == on


def plan_order(order, doc_file, po, today=None):
    """-> (patch|None, klaer [Text], konflikte [Text]) fuer EINE Order und EINEN Beleg."""
    today = today or dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    items = order.get("items") or []
    cells, klaer, konflikte, used = [], [], [], set()
    for wanted, color, qty, price, label in doc_positions(po):
        if price <= 0 or not wanted:
            continue
        idxs = [i for i, it in enumerate(items) if any(w in core.norm(it.get("name")) for w in wanted)]
        if not idxs:
            continue   # Style gehoert nicht zu dieser Order: kein Thema dieser Order
        hit, zero_seen = None, False
        for i in idxs:
            vs = items[i].get("variants") or []
            for j, v in enumerate(vs):
                if (i, j) in used or not _same_color(color, v.get("name"), len(vs) == 1):
                    continue
                oq = _order_qty(v)
                if not _is_zero(v):
                    ex = [a["price"] for a in v.get("amounts") or [] if a.get("price")]
                    if ex and any(abs(p - price) > PRICE_TOL * price for p in ex):
                        konflikte.append("UNSTIMMIG Preis %s: PLM %s, Beleg %s (nicht ueberschrieben)" % (label.strip(), _fmt(ex[0]), _fmt(price)))
                    continue
                zero_seen = True
                if qty > 0 and oq > 0 and abs(oq - qty) <= QTY_TOL * qty:
                    hit = (i, j, v, oq)
                    break
            if hit:
                break
        if hit:
            i, j, v, oq = hit
            used.add((i, j))
            cells.append({"item": i, "variant": j, "iname": items[i].get("name"), "vname": v.get("name"), "qty": oq, "price": _r2(price)})
        elif zero_seen or any(_is_zero(v) for i in idxs for v in items[i].get("variants") or []):
            klaer.append("%s: %s passt nicht zu bestehender Position (Style/Farbe/Menge %s)" % (WHY, label.strip(), _fmt(qty)))
    if not cells:
        return None, klaer, konflikte
    key = hashlib.sha1((order["id"] + doc_file + json.dumps([(c["item"], c["variant"], c["price"]) for c in cells])).encode()).hexdigest()[:8]
    text = "[%s pf:%s] PREIS NACHGETRAGEN aus %s: %s" % (today[:16], key, doc_file, "; ".join("%s %s = %s" % (c["iname"], c["vname"], _fmt(c["price"])) for c in cells))
    return {"id": order["id"], "title": order.get("title"), "orderNumber": order.get("orderNumber"), "file": doc_file, "marker": key, "text": text, "cells": cells}, klaer, konflikte


def _fmt(n):
    return ("%.4f" % n).rstrip("0").rstrip(".")


def plan(orders, docs, today=None):
    """orders: {id: order}; docs: [(Dateiname, parent_id, po)] -> {"patches": [...], "klaer": [{file,title,why}], "konflikte": [{file,title,why}]}.
    Mehrere Belege zur selben Order: erste Position gewinnt (eine Zelle wird nur einmal gesetzt, spaetere Belege sehen sie beim naechsten Lauf als befuellt)."""
    out = {"patches": [], "klaer": [], "konflikte": []}
    taken = {}
    for fname, pid, po in docs:
        o = orders.get(pid)
        if not o or not any(_is_zero(v) for it in o.get("items") or [] for v in it.get("variants") or []):
            continue
        patch, klaer, konf = plan_order(o, fname, po, today)
        t = o.get("title")
        if patch:
            cells = [c for c in patch["cells"] if (pid, c["item"], c["variant"]) not in taken]
            if cells:
                for c in cells:
                    taken[(pid, c["item"], c["variant"])] = fname
                patch["cells"] = cells
                same = [p for p in out["patches"] if p["id"] == pid]
                if same:   # zweiter Beleg zur selben Order im selben Lauf: erst im naechsten Lauf (Browser-Skript pro Order nur ein Patch)
                    continue
                out["patches"].append(patch)
        out["klaer"] += [{"file": fname, "title": t, "why": k} for k in klaer]
        out["konflikte"] += [{"file": fname, "title": t, "why": k} for k in konf]
    return out


def make_js(plan_, dry=True):
    tpl = (Path(__file__).parent / "price_fill_template.js").read_text()
    return tpl.replace("__PLAN__", json.dumps(plan_["patches"], ensure_ascii=False, separators=(",", ":"))).replace("__DRY__", "true" if dry else "false")


def report_lines(plan_, apply=False):
    L = []
    for p in plan_["patches"]:
        L.append("- %s Preis nachtragen (%s, %d Pos.): %s" % ("PREIS NACHGETRAGEN" if apply else "wuerde", p["file"], len(p["cells"]), p["title"]))
    L += ["- KLAERFALL %s (%s): %s" % (k["title"], k["file"], k["why"]) for k in plan_["klaer"]]
    L += ["- %s (%s, %s)" % (k["why"], k["title"], k["file"]) for k in plan_["konflikte"]]
    return L or ["- keine"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", default=str(ROOT / "output/intake/ctx_snapshot.json"))
    ap.add_argument("--inbox")
    a = ap.parse_args(argv)
    from plm_intake import docs_existing
    ctx = json.load(open(a.ctx))
    ctx["aliases"] = {}
    cands = []
    docs_existing.run(a.inbox or docs_existing.DEFAULT_INBOX, ctx, {}, ROOT / "output/intake/_price_fill_tmp", price_plan=cands)
    pl = plan({o["id"]: o for o in ctx["orders"]}, cands)
    print("\n".join(report_lines(pl)))
    print("Trockenlauf: nichts geschrieben (Ausfuehrung nur ueber auto_run --apply).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
