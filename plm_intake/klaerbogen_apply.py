"""Klaerbogen einlesen: Omars Wahlen (output/phase2/B20/klaerbogen.md, Spalte 'Wahl', oder CSV) -> event_overrides / po_aliases / overrides.

  python3 -m plm_intake.klaerbogen_apply                 Trockenlauf: zeigt, was geschrieben wuerde (Standard, schreibt nichts)
  python3 -m plm_intake.klaerbogen_apply --apply         schreibt NUR die lokalen Dateien in output/intake/ (Zustandsdateien laut cloud.STATE_FILES); kein Push in den Zustandszweig
  python3 -m plm_intake.klaerbogen_apply --csv wahl.csv  statt der .md: Zeilen 'Nr;Wahl' (z. B. 'F01;a')

Wahl je Fall: a | b (Kandidat) | info (kein Bestellbezug -> '__info__') | PO-ID (PO26-036) | #<Order-Nr> | Order-Titel | Order-ID. Leer = offen lassen.
Belege (B..): a | b (nur Alias der Beleg-Kennungen -> Order), skip (= overrides.json SKIP), create (= CREATE), info zaehlt als skip.
Ereignis-Fall: je Ereignis ein Eintrag Marker -> Order-ID in event_overrides.json; zusaetzlich werden eindeutige Kennungen (Container/B-L/Rechnung ...) als Alias gelernt
(gleiche Pruefung wie alias_learn.valid; Konflikt = '__mehrdeutig__'). Bestehende abweichende Eintraege werden nur mit --overwrite ersetzt.
Basis ist der neuere Zustand aus dem Git-Zweig (--state-ref), damit die lokale Datei keine Cloud-Eintraege verliert (lokale Zusatz-Eintraege bleiben erhalten).
"""
import argparse
import csv
import datetime as dt
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import alias_learn, core, events  # noqa: E402
from plm_intake import klaerbogen  # noqa: E402

INTAKE = ROOT / "output" / "intake"
B20 = ROOT / "output" / "phase2" / "B20"


def parse_md(text):
    """-> ({Nr: Wahl}, gen_id|None). Tabellenzeilen '| F01 | ... | <Wahl> |' (Pipes in Inhalten sind beim Erzeugen durch '¦' ersetzt)."""
    gen = re.search(r"<!-- klaerbogen:(\w+) -->", text)
    out = {}
    for ln in text.splitlines():
        m = re.match(r"\|\s*([FB]\d+)\s*\|", ln)
        if not m:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 2:
            out[m.group(1)] = cells[-1]
    return out, (gen.group(1) if gen else None)


def parse_csv(path):
    out = {}
    for row in csv.reader(open(path, newline=""), delimiter=";" if ";" in open(path).read(2000) else ","):
        if len(row) >= 2 and re.fullmatch(r"[FB]\d+", row[0].strip()):
            out[row[0].strip()] = row[1].strip()
    return out, None


def clean(w):
    return re.sub(r"[`*_\s]+", " ", str(w or "")).strip()


def resolve_order(w, bogen):
    """Freitext -> order_id (eindeutig) oder None."""
    orders = bogen["orders"]
    t = clean(w)
    if t in orders:
        return t
    m = re.search(r"PO\d{2}-\d{3}", t, re.I)
    if m:
        hit = [i for i, o in orders.items() if o["po_id"].upper() == m.group(0).upper()]
        return hit[0] if len(hit) == 1 else None
    m = re.fullmatch(r"#\s*(\d+)", t)
    if m:
        hit = [i for i, o in orders.items() if str(o["nr"]) == m.group(1)]
        return hit[0] if len(hit) == 1 else None
    hit = [i for i, o in orders.items() if core.norm(o["title"]) == core.norm(t)]
    return hit[0] if len(hit) == 1 else None


def decide(case, wahl, bogen):
    """-> (aktion, order_id|None, fehler|None). aktion: order | info | skip | create | offen"""
    w = clean(wahl)
    if not w or w == "-":
        return "offen", None, None
    lw = w.lower()
    if case["art"] == "beleg":
        if lw in ("skip", "info"):
            return "skip", None, None
        if lw == "create":
            return "create", None, None
    elif lw == "info":
        return "info", None, None
    if lw in ("a", "b"):
        k = next((c for c in case["kandidaten"] if c["key"] == lw), None)
        if not k:
            return "offen", None, "Wahl '%s', aber kein Kandidat %s" % (w, lw)
        return "order", k["order"]["id"], None
    oid = resolve_order(w, bogen)
    if oid:
        return "order", oid, None
    return "offen", None, "Wahl '%s' nicht eindeutig einer Order zuzuordnen" % w


def base_state(name, intake, state_ref, tmp):
    """Zustandsdatei: Zweig-Stand + lokale Zusatz-Eintraege (lokal gewinnt nur, wo der Zweig den Schluessel nicht hat)."""
    local = klaerbogen._load(intake / name, {})
    if not state_ref:
        return local
    d = Path(tmp) / "st"; d.mkdir(exist_ok=True)
    klaerbogen.state_from_ref(state_ref, d)
    remote = klaerbogen._load(d / name, None)
    if remote is None:
        return local
    merged = dict(remote)
    for k, v in local.items():
        merged.setdefault(k, v)
    return merged


def plan(bogen, choices, ev_ov, aliases, overrides, overwrite=False):
    """-> dict(zeilen, ev_ov, aliases, overrides, neu_alias, konflikte, fehler, ersetzt). Rein rechnerisch, ohne Schreiben."""
    ev_ov, aliases, overrides = dict(ev_ov), dict(aliases), dict(overrides)
    orders = [v["valid"] for v in bogen["orders"].values()]
    by_id = {o["id"]: o for o in orders}
    rows, errs, new_al, conf, skipped = [], [], [], [], []
    pairs = []
    for c in bogen["faelle"]:
        w = choices.get(c["nr"])
        act, oid, err = decide(c, w, bogen)
        if err:
            errs.append("%s: %s" % (c["nr"], err))
        if act == "offen":
            continue
        ziel = "kein Bestellbezug" if act == "info" else bogen["orders"][oid]["title"] if oid else act.upper()
        n_ev = len(c.get("ereignisse", [])) or 1
        zeile = {"nr": c["nr"], "vendor": c["vendor"], "aktion": act, "ziel": ziel, "n": n_ev, "konfidenz": c["konfidenz"], "ersetzt": 0}
        if c["art"] == "ereignis":
            val = events.INFO_OVERRIDE if act == "info" else oid
            for e in c["ereignisse"]:
                cur = ev_ov.get(e["marker"])
                if cur is not None and cur != val and not overwrite:
                    skipped.append("%s ev:%s: vorhanden %s, neu %s (nur mit --overwrite)" % (c["nr"], e["marker"], cur, val)); continue
                if cur is not None and cur != val:
                    zeile["ersetzt"] += 1
                ev_ov[e["marker"]] = val
            if oid:
                for e in c["ereignisse"]:
                    for k in e.get("idents") or []:
                        if alias_learn.valid(k, by_id[oid], (), orders):
                            pairs.append((k, oid, "Klaerbogen " + c["nr"]))
        else:
            if act in ("skip", "create"):
                cur = overrides.get(c["datei"])
                if cur is not None and cur != act.upper() and not overwrite:
                    skipped.append("%s %s: vorhanden %s (nur mit --overwrite)" % (c["nr"], c["datei"], cur)); continue
                overrides[c["datei"]] = act.upper()
            elif oid:
                for k in c.get("keys") or []:
                    if alias_learn.valid(k, by_id[oid], (), orders):
                        pairs.append((k, oid, "Klaerbogen " + c["nr"]))
        rows.append(zeile)
    res, new_al, conf = alias_learn.merge(aliases, pairs, orders, apply=False)
    return {"zeilen": rows, "ev_ov": ev_ov, "aliases": res, "overrides": overrides, "neu_alias": new_al, "konflikte": conf, "fehler": errs, "uebersprungen": skipped}


def write_json(path, data, sort=False):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=sort))
    tmp.replace(p)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--md", default=str(B20 / "klaerbogen.md"))
    ap.add_argument("--csv")
    ap.add_argument("--json", default=str(B20 / "klaerbogen.json"))
    ap.add_argument("--intake", default=str(INTAKE))
    ap.add_argument("--state-ref", default=klaerbogen.STATE_REF, help="'' = nur lokale Dateien als Basis")
    ap.add_argument("--apply", action="store_true", help="schreibt die lokalen Dateien (sonst Trockenlauf)")
    ap.add_argument("--overwrite", action="store_true", help="abweichende bestehende Eintraege ersetzen")
    a = ap.parse_args(argv)
    bogen = json.load(open(a.json))
    if a.csv:
        choices, gen = parse_csv(a.csv)
    else:
        choices, gen = parse_md(Path(a.md).read_text())
        if gen != bogen["gen_id"]:
            print("FEHLER: klaerbogen.md (Stand %s) und klaerbogen.json (Stand %s) gehoeren nicht zusammen. Bogen neu erzeugen oder die Wahlen per --csv uebergeben." % (gen, bogen["gen_id"]))
            return 2
    unknown = [k for k in choices if k not in {c["nr"] for c in bogen["faelle"]}]
    intake = Path(a.intake)
    tmp = tempfile.mkdtemp(prefix="klaerbogen_apply_")
    ev_ov = base_state("event_overrides.json", intake, a.state_ref, tmp)
    al = base_state("po_aliases.json", intake, a.state_ref, tmp)
    ov = base_state("overrides.json", intake, a.state_ref, tmp)
    p = plan(bogen, choices, ev_ov, al, ov, a.overwrite)
    L = ["# Klaerbogen einlesen (%s)" % ("SCHREIBEN" if a.apply else "TROCKENLAUF, nichts geschrieben"), ""]
    gew = [k for k, v in choices.items() if clean(v)]
    L.append("Wahlen: %d von %d Faellen ausgefuellt, %d offen." % (len(gew), len(bogen["faelle"]), len(bogen["faelle"]) - len(gew)))
    for z in p["zeilen"]:
        L.append("- %s %s [%s] -> %s (%d Ereignis%s%s)" % (z["nr"], z["vendor"][:28], z["konfidenz"], z["ziel"], z["n"], "se" if z["n"] != 1 else "", ", ersetzt %d" % z["ersetzt"] if z["ersetzt"] else ""))
    nE = sum(1 for k, v in p["ev_ov"].items() if ev_ov.get(k) != v)
    L += ["", "event_overrides neu/geaendert: %d | overrides.json: %d | neue Aliase: %d | Alias-Konflikte: %d" % (nE, sum(1 for k, v in p["overrides"].items() if ov.get(k) != v), len(p["neu_alias"]), len(p["konflikte"]))]
    L += ["- Alias %s -> %s (%s)" % (k, bogen["orders"].get(o, {}).get("title", o), s) for k, o, s in p["neu_alias"]]
    L += ["- ALIAS-KONFLIKT %s: %s <-> %s (auf mehrdeutig gesetzt)" % c for c in p["konflikte"]]
    L += ["- UEBERSPRUNGEN %s" % x for x in p["uebersprungen"]] + ["- FEHLER %s" % x for x in p["fehler"]] + ["- FEHLER unbekannte Nr %s" % x for x in unknown]
    print("\n".join(L))
    if not a.apply:
        return 1 if (p["fehler"] or unknown) else 0
    if p["fehler"] or unknown:
        print("\nAbbruch: erst die Fehler beheben (nichts geschrieben).")
        return 1
    bak = ROOT / "output" / "backup" / ("klaerbogen_vor_apply_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    bak.mkdir(parents=True, exist_ok=True)
    for n in ("event_overrides.json", "po_aliases.json", "overrides.json"):
        if (intake / n).exists():
            shutil.copy2(intake / n, bak / n)
    write_json(intake / "event_overrides.json", p["ev_ov"], sort=True)
    write_json(intake / "po_aliases.json", p["aliases"])
    write_json(intake / "overrides.json", p["overrides"])
    logf = B20 / "klaerbogen_entscheidungen.json"
    hist = klaerbogen._load(logf, [])
    hist.append({"zeit": dt.datetime.now().isoformat(timespec="seconds"), "gen_id": bogen["gen_id"], "zeilen": p["zeilen"], "neue_aliase": [[k, o] for k, o, _ in p["neu_alias"]]})
    write_json(logf, hist)
    print("\nGeschrieben (lokal): %s/{event_overrides,po_aliases,overrides}.json; Sicherung %s. Kein Push in den Zustandszweig." % (intake, bak))
    return 0


if __name__ == "__main__":
    sys.exit(main())
