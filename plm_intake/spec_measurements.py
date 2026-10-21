"""Spec-Dateien (Größentabellen aus Lieferanten-Mails) -> Reiter Measurements. Trockenlauf Standard.

  .venv/bin/python -m plm_intake.spec_measurements [--apply]

Quelle: output/phase2/B15/techpack_zuordnung.json (typ == 'Spec', mit zugeordneten Produkten). Pro Produkt nur die NEUESTE Tabelle.
Verpackungsmaß-Dateien (Kunde X 'Anlage_Verpackungsmasse', Shipping Marks) sind keine Größentabellen und werden nur aufgelistet.
Plausibilität: Einheit cm (inch nur bei eindeutiger Angabe, dann x2.54), Werte steigen mit der Größe, Größen passen zum Produkt im PLM.
Schreibweg wie measurements_p2: importProductMeasurements (Zeilen productSku/productName/pom/size/value/unit), nur Produkte OHNE Maße
(Inventur + frische Rücklesung), nur Größen, die das Produkt hat (XXL = 2XL). Nach --apply Rücklesung. Ohne --apply wird nichts ins PLM geschrieben.
Ausgabe: output/phase2/B16/measurements_plan.md + .json (bei --apply measurements_result.json)."""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "phase2" / "B16"
ANHAENGE = Path(os.path.expanduser("~/Library/CloudStorage/kontakt@firma.example/Meine Ablage/PLM-Mails/Anhaenge"))
SIZE_RE = re.compile(r"^(XXXS|XXS|2XS|3XS|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)(?![A-Z0-9\-/])")
CANON = {"XXL": "2XL", "XXXL": "3XL", "XXS": "2XS", "XXXS": "3XS"}
ORDER = ["3XS", "2XS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
PACK_RE = re.compile(r"verpackungsmasse|shipping mark", re.I)
XLS_JS = ("import sys,json,xlrd\nwb=xlrd.open_workbook(sys.argv[1])\n"
          "print(json.dumps({s.name:[[c for c in s.row_values(r)] for r in range(min(s.nrows,400))] for s in wb.sheets()},ensure_ascii=False,default=str))")


# ---------------------------------------------------------------- Lesen
def size_norm(c):
    """Zellinhalt -> kanonische Größe (XXL = 2XL) oder None."""
    if c is None or isinstance(c, (int, float)):
        return None
    s = re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(c))).upper()
    m = SIZE_RE.match(s)
    return CANON.get(m.group(1), m.group(1)) if m else None


def num(c):
    """Zahl aus Zelle ('62,00' -> 62.0) oder None."""
    if isinstance(c, bool) or c is None:
        return None
    if isinstance(c, (int, float)):
        return float(c)
    s = str(c).strip().replace(",", ".")
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def asciiness(s):
    return sum(ch.isascii() and ch.isalpha() for ch in s) / max(1, len(s))


def unit_of(texts):
    """'cm' | 'inch' | None (unklar). inch nur, wenn cm nirgends vorkommt."""
    t = " ".join(texts).lower()
    cm = bool(re.search(r"\bcm\b|\(cm\)|厘米|measurements\s*cm|unit\W*cm", t))
    inch = bool(re.search(r"\binch(es)?\b|\bin\.|\(in\)|unit\W*in\b", t))
    return "cm" if cm and not inch else "inch" if inch and not cm else None


def parse_grid(grid):
    """Gitter (Liste von Zeilen) -> Liste von Tabellen {sizes, rows, unit, tol_col, issues}. Mehrere Kopfzeilen = mehrere Tabellen."""
    tables, cur = [], None
    hdr_idx = []
    for i, row in enumerate(grid):
        cols = [(j, size_norm(c)) for j, c in enumerate(row)]
        cols = [(j, s) for j, s in cols if s]
        if len(cols) >= 2 and len({s for _, s in cols}) >= 2:
            # Kopf nur gültig, wenn in den nächsten 4 Zeilen Zahlen unter mindestens 2 seiner Größenspalten stehen (sonst Zufallstreffer wie Notiz 'S ... XXL')
            ok = any(sum((num(r2[j]) or 0) > 0 for j, _ in cols if j < len(r2)) >= min(2, len(cols)) for r2 in grid[i + 1:i + 5])
            if ok:
                hdr_idx.append((i, cols))
    for n, (i, cols) in enumerate(hdr_idx):
        end = hdr_idx[n + 1][0] if n + 1 < len(hdr_idx) else len(grid)
        seen, sz_cols, dups = set(), [], []
        for j, s in cols:
            if s in seen:
                dups.append(s)
                continue
            seen.add(s)
            sz_cols.append((j, s))
        first = sz_cols[0][0]
        last = sz_cols[-1][0]
        tol_col = next((j for j, c in enumerate(grid[i]) if j > last and re.search(r"tol|公差", str(c), re.I)), None)
        head_txt = [str(c) for r in grid[max(0, i - 6):i + 1] for c in r if isinstance(c, str)]
        t = {"header_row": i, "sizes": [s for _, s in sz_cols], "rows": [], "unit": unit_of(head_txt), "issues": [], "title": " ".join(head_txt)}
        if dups:
            t["issues"].append("Größen doppelt im Kopf (%s), nur erste Spalte je Größe gelesen" % ",".join(sorted(set(dups))))
        blank = 0
        for r in grid[i + 1:end]:
            vals, txt_cells = {}, []
            for j, s in sz_cols:
                c = r[j] if j < len(r) else None
                v = num(c)
                if v is not None:
                    vals[s] = v
                elif isinstance(c, str) and c.strip():
                    txt_cells.append(c.strip()[:40])
            pre = [str(c).strip() for c in r[:first] if isinstance(c, str) and c.strip()]
            if not vals:
                blank += 1
                continue
            blank = 0
            names = [c for c in pre if len(c) > 1 and asciiness(c) > 0.4 and not re.fullmatch(r"[A-Z0-9]{1,3}", c)]
            codes = [c for c in pre if re.fullmatch(r"[A-Z0-9]{1,4}", c)]
            if not names:
                names = [c for c in pre if re.search(r"[A-Za-z]", c)]
            if not names:
                continue
            tol = None
            if tol_col is not None and tol_col < len(r) and str(r[tol_col]).strip() not in ("", "None"):
                tol = str(r[tol_col]).strip()
            row = {"name": max(names, key=len).strip(), "code": codes[0] if codes else None, "values": vals, "tol": tol}
            if txt_cells:
                row["text_cells"] = txt_cells
            t["rows"].append(row)
        if t["rows"]:
            tables.append(t)
    return tables


def parse_pdf_text(pages):
    """PDF-Seiten (Text, eine Zelle je Zeile) -> Tabellen im selben Format: Kopf 'SIZE RANGE' + Größen, danach je Zeile Beschreibung + n Werte + Toleranz."""
    tables = []
    for pg in pages:
        tok = [x.strip() for x in pg.split("\n") if x.strip()]
        for k, t in enumerate(tok):
            if t.upper().startswith("SIZE RANGE"):
                break
        else:
            continue
        j = k + 1
        sizes = []
        while j < len(tok) and size_norm(tok[j]):
            sizes.append(size_norm(tok[j])); j += 1
        if len(sizes) < 2:
            continue
        n = len(sizes)
        txt, rows, skipped, head = [], [], [], [x for x in tok[:j]]
        while j < len(tok):
            run = []
            while j + len(run) < len(tok) and num(tok[j + len(run)]) is not None and len(run) < n:
                run.append(num(tok[j + len(run)]))
            if len(run) == n and txt:
                tol = None
                j += n
                if j < len(tok) and re.match(r"^\+?/?-?\s*\d", tok[j]) and tok[j].startswith(("+", "-")):
                    tol = tok[j]; j += 1
                # Beschreibung: Texte nach dem letzten Code (1-4 Großbuchstaben/Ziffern)
                code = None
                for q in range(len(txt) - 1, -1, -1):
                    if re.fullmatch(r"[A-Z0-9]{1,4}", txt[q]):
                        code = txt[q]
                        txt = txt[q + 1:]
                        break
                name = " ".join(txt).strip() or code
                rows.append({"name": name, "code": code, "values": dict(zip(sizes, run)), "tol": tol})
                txt = []
            elif 2 <= len(run) < n and txt:   # weniger Werte als Größen: Spaltenzuordnung nicht eindeutig -> Zeile nicht lesen
                skipped.append("%s (%d Werte, %d Größen)" % (" ".join(txt)[-40:], len(run), n))
                j += len(run); txt = []
            else:
                txt.append(tok[j]); j += 1
        rows = [r for r in rows if r["name"] and asciiness(r["name"]) > 0.4]
        if rows or skipped:   # auch ohne lesbare Zeilen anlegen, damit der Grund (unklare Spalten) im Bericht steht
            iss = ["Zeilen mit unklarer Spaltenzuordnung nicht gelesen: " + "; ".join(skipped[:6]) + (" ..." if len(skipped) > 6 else "")] if skipped else []
            tables.append({"header_row": 0, "sizes": sizes, "rows": rows, "unit": unit_of(head), "issues": iss})
    return tables


def read_tables(path):
    """Datei -> (Tabellen mit 'sheet', Fehlertext oder None)."""
    p = str(path)
    low = p.lower()
    try:
        if low.endswith(".pdf"):
            import fitz
            doc = fitz.open(p)
            tabs = parse_pdf_text([pg.get_text() for pg in doc])
            for t in tabs:
                t["sheet"] = "PDF"
            return tabs, None
        if low.endswith(".xls"):
            r = subprocess.run(["/usr/bin/python3", "-c", XLS_JS, p], capture_output=True, text=True, timeout=120)
            if r.returncode:
                return [], "xls nicht lesbar: " + r.stderr[-150:]
            sheets = json.loads(r.stdout)
        else:
            import openpyxl
            wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
            sheets = {ws.title: [list(x) for x in ws.iter_rows(values_only=True)][:400] for ws in wb.worksheets}
    except Exception as e:  # noqa: BLE001
        return [], "nicht lesbar: %s" % str(e)[:120]
    tabs = []
    for name, grid in sheets.items():
        for t in parse_grid(grid):
            t["sheet"] = name
            tabs.append(t)
    return tabs, None


# ---------------------------------------------------------------- Prüfen
def size_rank(s):
    return ORDER.index(s) if s in ORDER else 99


def monotone_check(table):
    """Werte steigen mit der Größe. Gibt (Zeilen mit Rückgang, Zeilen gesamt) zurück; kleine Ausnahme: Rückgang <= 0.5 cm."""
    bad = []
    for r in table["rows"]:
        seq = [(size_rank(s), v) for s, v in r["values"].items() if s in ORDER]
        seq.sort()
        drops = [(a[1], b[1]) for a, b in zip(seq, seq[1:]) if b[1] < a[1]]
        if drops:
            big = [d for d in drops if d[0] - d[1] > 0.5]
            bad.append({"name": r["name"], "drops": drops, "small": not big})
    return bad


def match_sizes(table_sizes, product_sizes):
    """Tabellen-Größen -> Schreibweise des Produkts (XXL = 2XL). Rückgabe: (map kanon->Produktgröße, nicht passend)."""
    pm = {}
    for s in product_sizes or []:
        k = size_norm(s) or s
        pm.setdefault(k, s)
    m = {s: pm[s] for s in table_sizes if s in pm}
    return m, [s for s in table_sizes if s not in pm]


def assess(table, product_sizes):
    """Beurteilt eine Tabelle: status ok|auffaellig|unplausibel plus Liste Auffälligkeiten; bei inch Umrechnung (nur eindeutig)."""
    iss = list(table.get("issues") or [])
    t = {**table, "rows": [dict(r) for r in table["rows"]]}
    unit = table.get("unit")
    allv = [v for r in t["rows"] for v in r["values"].values()]
    if unit == "inch":
        for r in t["rows"]:
            r["values"] = {s: round(v * 2.54, 2) for s, v in r["values"].items()}
        iss.append("Hinweis: Einheit inch laut Kopf eindeutig -> x2.54 umgerechnet")
    elif unit is None:
        iss.append("Hinweis: Einheit nicht angegeben, cm angenommen (Werte-Bereich 0-250 geprüft)")
    bad = "unplausibel"
    if not allv:
        return {"status": bad, "issues": iss + ["keine Werte"], "table": t, "sizes_map": {}}
    if min(allv) < 0:
        return {"status": bad, "issues": iss + ["negative Werte (Gradierungsdifferenzen, keine Maße)"], "table": t, "sizes_map": {}}
    if max(allv) > 250:
        return {"status": bad, "issues": iss + ["Wert über 250 cm"], "table": t, "sizes_map": {}}
    if len(t["sizes"]) < 2 and len(t["rows"]) < 3:
        iss.append("Hinweis: nur eine Größe")
    mono = monotone_check(t)
    real = [m for m in mono if not m["small"]]
    for m in mono:
        iss.append("%s%s: %s (%s)" % ("Hinweis: " if m["small"] else "", m["name"], "kleiner Rückgang (<=0.5 cm)" if m["small"] else "Werte fallen mit der Größe", ", ".join("%g>%g" % d for d in m["drops"])))
    for r in t["rows"]:
        if r.get("text_cells"):
            iss.append("%s: Text statt Zahl in Zelle (%s), übersprungen" % (r["name"], "; ".join(r["text_cells"])))
    names = [r["name"] for r in t["rows"]]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        iss.append("Messpunkt-Namen doppelt: %s" % ", ".join(sorted(dup)))
    smap, miss = match_sizes(t["sizes"], product_sizes)
    if miss:
        iss.append("Hinweis: Größen der Tabelle nicht im Produkt (werden nicht geschrieben): %s" % ",".join(miss))
    status = "ok"
    if real and len(real) > max(1, len(t["rows"]) // 4):
        status = bad
        iss.append("zu viele Zeilen ohne steigende Werte (%d von %d)" % (len(real), len(t["rows"])))
    elif any(not x.startswith("Hinweis:") for x in iss):
        status = "auffaellig"
    return {"status": status, "issues": iss, "table": t, "sizes_map": smap}


def pick_table(tabs, sku=None):
    """Haupttabelle einer Datei für ein Produkt. Eine Tabelle -> diese. Mehrere -> nur wenn genau eine den SKU in Blattname/Titel trägt
    (Blätter können Kopien anderer Styles sein), sonst None (mehrdeutig, nicht raten). Ohne sku (nur Bewertung) die mit den meisten Messpunkten."""
    tabs = [t for t in tabs if t["rows"]] or tabs
    if len(tabs) <= 1:
        return tabs[0] if tabs else None
    if sku is None:
        return max(tabs, key=lambda t: (len(t["rows"]), len(t["sizes"])))
    k = re.sub(r"[^A-Z0-9]", "", sku.upper())
    hit = [t for t in tabs if k and k in re.sub(r"[^A-Z0-9]", "", (str(t.get("sheet", "")) + t.get("title", "")).upper())]
    return hit[0] if len(hit) == 1 else None


def fresh_measure_flags(ids):
    """Frische Rücklesung (nur lesen): {produkt_id: True, wenn productMeasurementMetadata Messzeilen hat}. Bei Fehler {} (dann zählt nur die Inventur)."""
    from plm_intake import batch_plan as bp
    if "meta:" not in bp.DETAIL_JS:
        bp.DETAIL_JS = bp.DETAIL_JS.replace("    ident:", "    meta: '{ productMeasurementMetadata(productId:$productId){ id metadata } }',\n    ident:")
    det = bp.fetch_details(list(ids))
    return {pid: any((m.get("metadata") or {}) for m in ((det.get(pid) or {}).get("meta") or [])) for pid in ids if pid in det}


def newest_per_product(entries):
    """entries: [{datum, datei, pid, ...}] -> je Produkt-ID nur der neueste (Datum, dann Dateiname), übrige als ältere."""
    best, older = {}, []
    for e in entries:
        cur = best.get(e["pid"])
        if cur is None or (e["datum"], e["datei"]) > (cur["datum"], cur["datei"]):
            if cur:
                older.append(cur)
            best[e["pid"]] = e
        else:
            older.append(e)
    return best, older


def make_lines(sku, pname, table, smap):
    """Importzeilen im Format von measurements_p2: productSku, productName, pom, size, value, unit."""
    out = []
    for r in table["rows"]:
        for s, v in r["values"].items():
            if s in smap:
                out.append({"productSku": sku, "productName": pname, "pom": r["name"], "size": smap[s], "value": "%g" % v, "unit": "cm"})
    return out


def classify(product, assessed, has_measure):
    """Entscheidung je Produkt: vorhanden | schreiben | blockiert (Größen) | unplausibel."""
    if has_measure:
        return "vorhanden", "Produkt hat schon Maße - nicht anfassen"
    if assessed is None:
        return "unlesbar", "keine Tabelle gelesen"
    if assessed["status"] == "unplausibel":
        return "unplausibel", "; ".join(assessed["issues"][-2:])
    if not assessed["sizes_map"]:
        return "blockiert", "keine Tabellen-Größe passt zu den Produkt-Größen (%s)" % ",".join(product.get("sizes") or [])
    return "schreiben", ""


# ---------------------------------------------------------------- Lauf
def build(zuordnung, products, inv, fresh_meta=None, reader=read_tables, anhaenge=ANHAENGE):
    """Baut den Plan. fresh_meta: {produkt_id: True/False} aus frischer Rücklesung (None = nur Inventur)."""
    P = {p["id"]: p for p in products}
    spec = [e for e in zuordnung if e.get("typ") == "Spec"]
    pack = [e for e in spec if PACK_RE.search(e["datei"])]
    tabs_e = [e for e in spec if not PACK_RE.search(e["datei"])]
    assigned = [e for e in tabs_e if e.get("ids")]
    unassigned = [e for e in tabs_e if not e.get("ids")]
    entries = [{"datum": e["datum"], "datei": e["datei"], "pid": pid} for e in assigned for pid in e["ids"] if pid in P]
    best, older = newest_per_product(entries)
    cache, plan = {}, []
    for pid, e in sorted(best.items(), key=lambda kv: P[kv[0]]["sku"]):
        p = P[pid]
        if e["datei"] not in cache:
            cache[e["datei"]] = reader(anhaenge / e["datei"])
        tabs, err = cache[e["datei"]]
        ntab = len(tabs)
        tab = pick_table(tabs, p["sku"])
        if tabs and tab is None:
            err = "mehrdeutig: Datei enthält %d Tabellen (%s), keine trägt eindeutig den SKU %s" % (ntab, ", ".join(str(t.get("sheet")) for t in tabs), p["sku"])
        elif tab is not None and not tab["rows"]:
            err, tab = "; ".join(tab["issues"]) or "keine Größentabelle erkannt", None
        elif tab is None and not err:
            err = "keine Größentabelle erkannt"
        has = bool(inv.get(pid, {}).get("masse")) or bool((fresh_meta or {}).get(pid))
        a = assess(tab, p.get("sizes")) if tab else None
        status, why = classify(p, a, has)
        item = {"sku": p["sku"], "product_id": pid, "name": p.get("name"), "status": status, "grund": why or err or "",
                "quelle": e["datei"], "datum": e["datum"], "produkt_groessen": p.get("sizes") or [],
                "aeltere_fassungen": sorted(o["datei"] for o in older if o["pid"] == pid)}
        if a:
            t = a["table"]
            item.update({"tabellen_in_datei": ntab, "blatt": t.get("sheet"), "tabellen_groessen": t["sizes"], "einheit": t.get("unit") or "cm (angenommen)",
                         "messpunkte": [{"name": r["name"], "code": r.get("code"), "tol": r.get("tol"), "values": r["values"]} for r in t["rows"]],
                         "bewertung": a["status"], "auffaelligkeiten": a["issues"]})
            if status == "schreiben":
                item["lines"] = make_lines(p["sku"], p.get("name"), t, a["sizes_map"])
            if ntab > 1:
                item["auffaelligkeiten"].append("Datei enthält %d Tabellen, gewählt Blatt %s (trägt den SKU im Titel)" % (ntab, t.get("sheet")))
        elif err:
            item["auffaelligkeiten"] = [err]
            if status != "vorhanden":
                item["status"] = "unlesbar"
        plan.append(item)
    loose = []
    for e in sorted({x["datei"]: x for x in unassigned}.values(), key=lambda x: (x["datum"], x["datei"])):
        if e["datei"] not in cache:
            cache[e["datei"]] = reader(anhaenge / e["datei"])
        tabs, err = cache[e["datei"]]
        tab = pick_table(tabs)
        row = {"datei": e["datei"], "datum": e["datum"], "grund": "kein Produkt zugeordnet"}
        if tab is not None and tab["rows"]:
            a = assess(tab, None)
            row.update({"lesbar": True, "groessen": tab["sizes"], "messpunkte": len(tab["rows"]), "bewertung": a["status"]})
        else:
            row.update({"lesbar": False, "fehler": err or "keine Größentabelle erkannt"})
        loose.append(row)
    return {"plan": plan, "verpackung": sorted({e["datei"] for e in pack}), "ohne_zuordnung": loose}


def report(res, apply=False, result=None):
    pl = res["plan"]
    by = lambda st: [x for x in pl if x["status"] == st]
    w, v = by("schreiben"), by("vorhanden")
    L = ["# Spec-Größentabellen -> Measurements (%s)" % ("APPLY" if apply else "TROCKENLAUF, nichts ins PLM geschrieben"), "",
         "Quelle: B15/techpack_zuordnung.json (typ Spec). Je Produkt nur die neueste Fassung. Einheit cm.", "",
         "## Übersicht", "",
         "- Produkte mit zugeordneter Größentabelle: %d" % len(pl),
         "- würde schreiben (Produkt ohne Maße, Größen passen): %d" % len(w),
         "- vorhanden, nicht anfassen: %d" % len(v),
         "- blockiert (Produktgrößen passen nicht, z. B. ONE SIZE): %d" % len(by("blockiert")),
         "- unplausibel: %d, unlesbar: %d" % (len(by("unplausibel")), len(by("unlesbar"))),
         "- Verpackungsmaß-Dateien (keine Größentabellen): %d" % len(res["verpackung"]),
         "- Spec-Dateien ohne Produktzuordnung: %d (lesbar: %d)" % (len(res["ohne_zuordnung"]), sum(1 for x in res["ohne_zuordnung"] if x["lesbar"])), ""]
    L += ["## Würde schreiben", ""] + (["- keine"] if not w else [])
    for x in w:
        L.append("- %s (%s) <- %s (%s): %d Messpunkte, Größen %s, %d Zeilen%s" % (x["sku"], x["name"], x["quelle"], x["datum"], len(x["messpunkte"]), ",".join(x["tabellen_groessen"]), len(x["lines"]), " | " + "; ".join(x["auffaelligkeiten"]) if x["auffaelligkeiten"] else ""))
    L += ["", "## Blockiert / unplausibel / unlesbar", ""]
    for st in ("blockiert", "unplausibel", "unlesbar"):
        for x in by(st):
            L.append("- [%s] %s <- %s (%s): %s%s" % (st, x["sku"], x["quelle"], x["datum"], x["grund"], " | Tabelle: %d Messpunkte, Größen %s" % (len(x["messpunkte"]), ",".join(x["tabellen_groessen"])) if x.get("messpunkte") else ""))
    L += ["", "## Vorhanden, nicht anfassen", ""] + ["- %s <- %s (%s)%s" % (x["sku"], x["quelle"], x["datum"], " | " + "; ".join(a for a in x.get("auffaelligkeiten", []) if not a.startswith("Hinweis:"))[:200] if any(not a.startswith("Hinweis:") for a in x.get("auffaelligkeiten", [])) else "") for x in v]
    older = [(x["sku"], o) for x in pl for o in x["aeltere_fassungen"]]
    L += ["", "## Ältere Fassungen (nicht verwendet)", ""] + ["- %s: %s" % o for o in older]
    L += ["", "## Verpackungsmaß-Dateien (nur aufgelistet, keine Größentabellen)", ""] + ["- %s" % f for f in res["verpackung"]]
    L += ["", "## Spec-Dateien ohne Produktzuordnung", ""]
    for x in res["ohne_zuordnung"]:
        L.append("- %s (%s): %s" % (x["datei"], x["datum"], ("lesbar, %d Messpunkte, Größen %s, %s" % (x["messpunkte"], ",".join(x["groessen"]), x["bewertung"])) if x["lesbar"] else "nicht lesbar: " + x["fehler"]))
    if w:
        x = w[0]
        L += ["", "## Beispiel: %s (%s)" % (x["sku"], x["quelle"]), "", "| Messpunkt | Code | Tol | " + " | ".join(x["tabellen_groessen"]) + " |", "|---|---|---|" + "---|" * len(x["tabellen_groessen"])]
        for m in x["messpunkte"]:
            L.append("| %s | %s | %s | " % (m["name"], m["code"] or "", m["tol"] or "") + " | ".join("%g" % m["values"][s] if s in m["values"] else "" for s in x["tabellen_groessen"]) + " |")
    if result:
        L += ["", "## Rücklesung", ""] + ["- %s" % r for r in result.get("rueck", [])]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="schreibt Produkte mit Status 'schreiben' und Bewertung ok (sonst nur Plan)")
    ap.add_argument("--auch-auffaellig", action="store_true", help="mit --apply auch Tabellen mit Bewertung auffaellig")
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    zuord = json.loads((ROOT / "output/phase2/B15/techpack_zuordnung.json").read_text())
    inv = {r["id"]: r for r in json.loads((ROOT / "output/phase2/B0/inventur.json").read_text())["rows"]}
    products = fetch_all(plm_client.call, "products")
    res0 = build(zuord, products, inv)
    ids = [x["product_id"] for x in res0["plan"] if x["status"] != "vorhanden"]
    fresh = fresh_measure_flags(ids) if ids else {}
    res = build(zuord, products, inv, fresh_meta=fresh)
    res["frische_ruecklesung"] = {"geprueft": len(ids), "antworten": len(fresh)}
    result = None
    if a.apply:
        todo = [x for x in res["plan"] if x["status"] == "schreiben" and (x["bewertung"] == "ok" or a.auch_auffaellig)]
        result = {"rueck": []}
        if todo:
            from plm_intake import batch_plan as bp
            from plm_intake.measurements_p2 import IMPORT_JS
            import tempfile
            js = IMPORT_JS.replace("__BATCHES__", json.dumps([x["lines"] for x in todo], ensure_ascii=False))
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                f.write(js)
            r = subprocess.run(["node", str(bp.BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(bp.BROWSER), timeout=900)
            result["import"] = json.loads(r.stdout) if r.returncode == 0 else {"fehler": r.stderr[-500:]}
            back = bp.fetch_details([x["product_id"] for x in todo])
            for x in todo:
                n = len([m for m in (back.get(x["product_id"]) or {}).get("meta") or [] if m.get("metadata")])
                result["rueck"].append("%s: %d Messzeilen im PLM (geplant %d Messpunkte) %s" % (x["sku"], n, len(x["messpunkte"]), "OK" if n >= len(x["messpunkte"]) else "ABWEICHUNG"))
        else:
            result["rueck"].append("nichts zu schreiben")
        (OUT / "measurements_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    md = report(res, a.apply, result)
    (OUT / "measurements_plan.md").write_text(md)
    (OUT / "measurements_plan.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(md)


if __name__ == "__main__":
    main()
