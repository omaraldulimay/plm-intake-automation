"""Quellenprüfung Phase 2: kein Wert ohne wörtliches Zitat aus der Quelle, Summen stimmen, zweite Lesung stimmt überein.

  python3 -m plm_intake.phase2_check output/phase2/<lieferant> [--cross]   Exit 1 bei Abweichung (Stopp), Bericht check_report.md

Verzeichnis je Lieferant:  src/<fileId>.txt (wörtlicher Quelltext), extract/<fileId>.json (Leser), check/<fileId>.json (Prüf-Agent, nur für --cross)
Extrakt-Format:
  {"fileId": "...", "facts": [{"key": "order.total", "value": 70000, "src": {"zeile": 12, "zitat": "Total USD 70,000.00"}}, ...],
   "order": {"total": 70000, "pieces": 5000, "items": [{"qty": 3500, "price": 14, "sum": 49000}], "payments": [{"amount": 21000}]},
   "measurements": {"sizes": ["S","M"], "rows": [{"name": "Brustumfang", "values": {"S": 50, "M": 52}}]},
   "composition": [{"material": "Baumwolle", "percent": 80}]}
Fehlender Wert: value null + "fehlt_grund" (kein Fehler, aber im Bericht)."""
import argparse
import json
import re
import sys
from pathlib import Path

BANK_RX = re.compile(r"(?i)\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b|\bswift\b|\bbic\b\s*[:=]|\biban\b|account\s*(no|number)|kontonummer")
TOL_SUM = 0.01


def norm_text(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def num_variants(v):
    """Zahl in den üblichen Schreibweisen (70000 -> 70000, 70,000, 70.000, 70 000, mit .00/,00)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return [norm_text(v)]
    out = set()
    i = int(round(f)); dec = abs(f - i) > 1e-9
    plain = ("%.2f" % f) if dec else str(i)
    out.add(plain); out.add(plain.replace(".", ","))
    for extra in (repr(f).rstrip("0").rstrip(".") if dec else str(i) + ".0", ("%.3f" % f).rstrip("0") if dec else str(i) + ",0"):
        out.add(extra); out.add(extra.replace(".", ","))
    if dec and abs(f * 10 - round(f * 10)) < 1e-9:
        out.add("%.1f" % f); out.add(("%.1f" % f).replace(".", ","))
    for sep in (",", ".", " ", " ", "'"):
        grp = "{:,}".format(int(f) if dec else i).replace(",", sep)
        out.add(grp)
        if dec:
            out.add(grp + ("." if sep != "." else ",") + ("%.2f" % f).split(".")[1])
        else:
            out.add(grp + ".00"); out.add(grp + ",00")
    return sorted(out, key=len, reverse=True)


def value_in(v, text):
    """Steht der Wert (Zahl in einer üblichen Schreibweise oder Text) im Zitat? Zahlen nur als eigenständiges Token."""
    t = norm_text(text)
    if isinstance(v, bool) or v is None:
        return True
    if isinstance(v, (int, float)):
        for s in num_variants(v):
            if re.search(r"(?<![\d.,])" + re.escape(s.lower()) + r"(?![\d]|[.,]\d)", t):
                return True
        return False
    return norm_text(v) in t


def check_quotes(extract, src_text):
    errs, nulls = [], 0
    S = norm_text(src_text)
    for f in extract.get("facts") or []:
        k = f.get("key")
        if f.get("value") is None:
            nulls += 1
            continue
        z = (f.get("src") or {}).get("zitat")
        if not z:
            errs.append("%s: kein Zitat" % k); continue
        if norm_text(z) not in S:
            errs.append("%s: Zitat steht nicht wörtlich in der Quelle: %r" % (k, str(z)[:80])); continue
        if not value_in(f["value"], z):
            errs.append("%s: Wert %r steht nicht im Zitat %r" % (k, f["value"], str(z)[:80]))
    return errs, nulls


def check_sums(extract):
    errs = []
    o = extract.get("order") or {}
    items, pays = o.get("items") or [], o.get("payments") or []
    tot = o.get("total")
    if items and all(i.get("sum") is not None for i in items) and tot is not None:
        s = sum(float(i["sum"]) for i in items)
        if abs(s - float(tot)) > TOL_SUM:
            errs.append("Summe Positionen %.2f != Total %.2f" % (s, float(tot)))
    for i in items:
        if i.get("qty") is not None and i.get("price") is not None and i.get("sum") is not None and abs(float(i["qty"]) * float(i["price"]) - float(i["sum"])) > 0.05 * max(1, float(i["qty"])) / 100 + TOL_SUM:
            errs.append("Position %s: Menge x Preis != Summe" % (i.get("name") or i.get("style") or "?"))
    if pays and tot is not None:
        s = sum(float(p["amount"]) for p in pays if p.get("amount") is not None)
        if abs(s - float(tot)) > TOL_SUM:
            errs.append("Summe Raten %.2f != Total %.2f" % (s, float(tot)))
    if items and o.get("pieces") is not None and all(i.get("qty") is not None for i in items):
        s = sum(float(i["qty"]) for i in items)
        if abs(s - float(o["pieces"])) > 0.5:
            errs.append("Summe Stück %d != Gesamtstück %d" % (s, o["pieces"]))
    return errs


def check_measurements(extract, product_sizes=None, tol=0.5):
    errs = []
    m = extract.get("measurements")
    if not m:
        return errs
    sizes = m.get("sizes") or []
    if product_sizes is not None and [norm_text(x) for x in sizes] != [norm_text(x) for x in product_sizes]:
        errs.append("Größen der Tabelle %s != Produktgrößen %s" % (sizes, product_sizes))
    for r in m.get("rows") or []:
        vals = [r["values"].get(s) for s in sizes if r.get("values", {}).get(s) is not None]
        if any(b < a - tol for a, b in zip(vals, vals[1:])) and not r.get("ausnahme"):
            errs.append("Messpunkt %s nicht monoton mit der Größe: %s" % (r.get("name"), vals))
    return errs


def check_composition(extract):
    c = extract.get("composition")
    if not c:
        return []
    s = sum(float(x.get("percent") or 0) for x in c)
    return [] if abs(s - 100) < 0.01 else ["Zusammensetzung %.1f %% statt 100 %%" % s]


def check_bank(extract):
    txt = json.dumps(extract, ensure_ascii=False)
    # Zitate dürfen Bankzeilen enthalten, geschrieben werden sie nie: nur Felder außerhalb von src prüfen
    stripped = re.sub(r'"src":\s*\{[^}]*\}', '"src":{}', txt)
    m = BANK_RX.search(stripped)
    return ["Bankdaten im Extrakt: %r" % m.group(0)] if m else []


def flatten(extract):
    return {f["key"]: f.get("value") for f in extract.get("facts") or [] if f.get("key")}


def _canon(x):
    """Vergleichbarer Kern eines Extrakts (unabhängig von Feldnamen der Agenten): Bestellung und Maßtabelle."""
    o = x.get("order") or {}
    r2 = lambda v: None if v in (None, "") else round(float(v), 2)
    agg = {}
    for i in o.get("items") or []:  # je Preis aufsummiert: unabhängig davon, ob ein Leser je Größe oder je Position zählt
        k = r2(i.get("price"))
        if not k:  # Packlisten ohne Preis: nur Gesamtstück zählt (order.pieces)
            continue
        agg[k] = round(agg.get(k, 0) + float(i.get("qty") or 0), 2)
    items = sorted(agg.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
    m = x.get("measurements") or {}
    rows = sorted((tuple(sorted((str(k), r2(v)) for k, v in (r.get("values") or {}).items() if v not in (None, ""))))
                  for r in m.get("rows") or [] if any(v not in (None, "") for v in (r.get("values") or {}).values()))
    return {"order.total": r2(o.get("total")), "order.pieces": r2(o.get("pieces")), "order.items": items,
            "measurements.sizes": [str(z) for z in m.get("sizes") or []], "measurements.rows": rows}


def cross(a, b):
    ca, cb = _canon(a), _canon(b)
    errs = ["%s: Leser %r != Prüf-Agent %r" % (k, ca[k], cb[k]) for k in ca if ca[k] != cb[k]]
    fa, fb = flatten(a), flatten(b)
    for k in sorted(set(fa) & set(fb)):  # gleiche Schlüssel: Werte müssen gleich sein; Schlüsselnamen selbst sind frei
        va, vb = fa[k], fb[k]
        if va is None or vb is None:
            continue
        num = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (va, vb))
        if not num:  # Texte (Datumsformat, Incoterm-Zusatz) nicht vergleichen, nur Zahlen
            continue
        if abs(float(va) - float(vb)) >= 0.005:
            errs.append("%s: Leser %r != Prüf-Agent %r" % (k, va, vb))
    return errs


def run(d, do_cross=False, product_sizes=None):
    d = Path(d)
    rep, fatal = ["# Quellenprüfung %s" % d.name, ""], 0
    files = sorted((d / "extract").glob("*.json"))
    if not files:
        rep.append("KEINE Extrakte gefunden")
        fatal += 1
    for ef in files:
        ex = json.loads(ef.read_text())
        sf = d / "src" / (ef.stem + ".txt")
        errs = []
        if not sf.exists():
            errs.append("Quelltext fehlt: %s" % sf.name)
            nulls = 0
        else:
            qe, nulls = check_quotes(ex, sf.read_text())
            errs += qe
        errs += check_sums(ex) + check_measurements(ex, (product_sizes or {}).get(ef.stem)) + check_composition(ex) + check_bank(ex)
        if do_cross:
            cf = d / "check" / ef.name
            if not cf.exists():
                errs.append("Prüf-Agent-Datei fehlt")
            else:
                errs += cross(ex, json.loads(cf.read_text()))
        rep.append("- %s %s%s" % ("FEHLER" if errs else "ok", ef.name, " (%d Felder null)" % nulls if nulls else ""))
        rep += ["    - " + e for e in errs]
        fatal += len(errs)
    rep += ["", "Ergebnis: %s" % ("STOPP, %d Abweichungen" % fatal if fatal else "alles stimmt (%d Dateien)" % len(files))]
    (d / "check_report.md").write_text("\n".join(rep))
    return fatal, "\n".join(rep)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("--cross", action="store_true")
    a = ap.parse_args(argv)
    fatal, text = run(a.dir, a.cross)
    print(text)
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
