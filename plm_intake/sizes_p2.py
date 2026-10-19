"""Fehlende Groesse 3XL an PLM-Produkten ergaenzen (Plan + Rueckpruefung).

  python3 -m plm_intake.sizes_p2 [--skus A,B]           TROCKENLAUF (Standard): Bericht output/phase2/sizes_3xl_<Zeit>.md, schreibt NICHTS
  python3 -m plm_intake.sizes_p2 --apply [--skus A,B]   liest per REST zurueck, ob die geplanten Groessen jetzt da sind (Schreiben selbst nur per Lifecycle-MCP
                                                         manage_product_sizes add sizeName=3XL afterSize=<XXL-Schreibweise>; es gibt keinen REST-Weg dafuer)

Regel: 3XL nur, wenn Plenty (logistics.skus) fuer das Produkt 3XL-Zeilen mit gueltiger EAN hat. Hat das Produkt schon eine 3XL-Groesse in anderer Schreibweise
(3XXL, XXXL, 3X), wird nichts angelegt (Dublette) -> 'Schreibweise klaeren'. Mehrere PLM-Produkte mit gleicher SKU -> 'mehrdeutig', nichts geplant."""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import barcodes, core  # noqa: E402

DEFAULT_SKUS = ["XW-041", "XW-124", "HY29582", "HY29583", "HY29587", "AL29008"]
OUT = ROOT / "output" / "phase2"


def titles(p):
    return [(s.get("title") if isinstance(s, dict) else str(s)) for s in (p.get("sizes") or [])]


def is_3xl(t):
    return re.sub(r"[\s\-]+", "", str(t or "").upper()) in ("3XL", "XXXL", "3XXL", "3X")


def is_xxl(t):
    return str(t or "").upper().strip() in ("XXL", "2XL", "XXL.")


def plan(product, plenty_rows, same_sku_count=1):
    """-> dict(action: add|skip, reason, afterSize, sizes)"""
    sz = titles(product)
    if same_sku_count > 1:
        return {"action": "skip", "reason": "mehrdeutig: %d PLM-Produkte mit dieser SKU" % same_sku_count, "sizes": sz}
    have = [t for t in sz if is_3xl(t)]
    if have:
        exact = "3XL" in have
        return {"action": "skip", "reason": "3XL schon vorhanden" if exact else "3XL-Groesse in anderer Schreibweise vorhanden (%s) -> Schreibweise klaeren, keine Dublette anlegen" % ",".join(have), "sizes": sz}
    p3 = [r for r in plenty_rows if barcodes.norm_size(r["size"]) == "3XL" and barcodes.ean_ok(r["ean"])]
    if not p3:
        return {"action": "skip", "reason": "Plenty hat keine 3XL-EAN", "sizes": sz}
    xx = [t for t in sz if is_xxl(t)]
    if not xx:
        return {"action": "skip", "reason": "keine XXL/2XL-Groesse als Anker", "sizes": sz}
    return {"action": "add", "reason": "Plenty 3XL: %d Zeilen mit gueltiger EAN" % len(p3), "afterSize": xx[-1], "sizes": sz}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skus"); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    skus = [x.strip() for x in a.skus.split(",")] if a.skus else DEFAULT_SKUS
    products = fetch_all(plm_client.call, "products")
    prows = barcodes.plenty_rows(skus)
    rep = ["# 3XL-Groessen (%s)" % ("RUECKPRUEFUNG" if a.apply else "TROCKENLAUF"), "", "Stand %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    bad = 0
    for s in skus:
        k = core.norm(s)
        hits = [p for p in products if core.norm(p.get("sku")) == k]
        if not hits:
            rep.append("- %s: kein PLM-Produkt" % s); continue
        for p in hits:
            pl = plan(p, prows.get(k, []), len(hits))
            line = "- %s (%s, %s): %s -> %s%s | Groessen jetzt: %s" % (s, p["id"], p.get("name"), pl["action"].upper(), pl["reason"], (" | MCP: manage_product_sizes add 3XL afterSize=%s" % pl["afterSize"]) if pl["action"] == "add" else "", ",".join(pl["sizes"]))
            if a.apply and pl["action"] == "add":
                bad += 1; line += " | ABWEICHUNG: 3XL fehlt noch"
            rep.append(line)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / ("sizes_3xl_%s.md" % dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    f.write_text("\n".join(rep)); print("\n".join(rep)); print(f)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
