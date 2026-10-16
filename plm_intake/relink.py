"""Nachverknuepfen: Positionen bestehender Orders ohne Produktlink bekommen Produkt + variantId, wenn das Produkt inzwischen im PLM existiert.
Aendert NUR product/variantId, nie Mengen, Preise, Zahlungen. Plan ist reine Funktion (testbar); Ausfuehrung per Browser-Skript mit Vorher/Nachher-Vergleich.
  python3 -m plm_intake.relink [--ctx snapshot.json]   -> schreibt output/intake/relink_<zeit>.js (nur wenn etwas zu tun ist) und druckt den Plan"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402


def item_sku(name):
    m = re.match(r"\s*([A-Za-z]{1,6}\d*[-_ ]?\d{2,}[A-Za-z]?(?:-\d+)?)", str(name or ""))
    return m.group(1) if m else None


def plan(orders, products, only_titles=None):
    by_sku = {core.norm(p["sku"]): p for p in products if p.get("sku")}
    out = []
    for o in orders:
        if only_titles and o["title"] not in only_titles:
            continue
        links, skipped = [], []
        for idx, it in enumerate(o.get("items") or []):
            if it.get("product"):
                continue
            sku = item_sku(it.get("name"))
            prod = by_sku.get(core.norm(sku)) if sku else None
            if not prod:
                continue
            pvars = {core.norm_color(v["name"]): v["id"] for v in prod.get("variants") or []}
            psizes = prod.get("sizes") or []
            vmap, bad = {}, []
            for v in it.get("variants") or []:
                vid = pvars.get(core.norm_color(v.get("name")))
                if not vid:
                    bad.append("Farbe '%s' fehlt am Produkt" % v.get("name"))
                    continue
                miss = [a["key"] for a in v.get("amounts") or [] if a["key"] not in psizes]
                if miss:
                    bad.append("Groessen %s von '%s' nicht am Produkt %s (nicht umbenannt, bitte pruefen)" % (miss, v.get("name"), prod["sku"]))
                    continue
                vmap[v["name"]] = vid
            if bad:
                skipped.append({"item": it.get("name"), "sku": prod["sku"], "reasons": bad})
                continue
            links.append({"index": idx, "name": it["name"], "product": prod["id"], "sku": prod["sku"], "variants": vmap})
        if links or skipped:
            out.append({"id": o["id"], "title": o["title"], "orderNumber": o.get("orderNumber"), "links": links, "skipped": skipped})
    return out


def make_js(plan_):
    tpl = (Path(__file__).parent / "relink_template.js").read_text()
    return tpl.replace("__PLAN__", json.dumps([p for p in plan_ if p["links"]], ensure_ascii=False, separators=(",", ":")))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx")
    ap.add_argument("--titles", nargs="*", help="nur diese Order-Titel")
    a = ap.parse_args(argv)
    if a.ctx:
        ctx = json.load(open(a.ctx))
    else:
        from plm_intake.context import load_context
        ctx = load_context()
    pl = plan(ctx["orders"], ctx["products"], set(a.titles) if a.titles else None)
    for p in pl:
        print("#%s %s" % (p["orderNumber"], p["title"]))
        for l in p["links"]:
            print("   LINK  %-45s -> %s (%d Varianten)" % (l["name"][:45], l["sku"], len(l["variants"])))
        for s in p["skipped"]:
            print("   SKIP  %-45s %s" % (s["item"][:45], "; ".join(s["reasons"])))
    if any(p["links"] for p in pl):
        f = ROOT / "output" / "intake" / ("relink_%s.js" % dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
        f.write_text(make_js(pl))
        print("Browser-Skript:", f)
    else:
        print("Nichts zu verknuepfen.")


if __name__ == "__main__":
    main()
