"""Batch 10 Teil B: Leser/Prüfer-Abweichungen (STOPP.md) feldweise schlichten, ohne Raten.

  python3 -m plm_intake.stopp_resolve            TROCKENLAUF: output/phase2/B10/stopp_resolve.md
  python3 -m plm_intake.stopp_resolve --apply    schreibt die geschlichtete Fassung in extract/ UND check/ (Originale in <lieferant>/stopp_orig/), danach läuft der normale Phase-2-Ablauf

Verglichen wird der Kern (phase2_check._canon: Total, Gesamtstück, Positionen je Preis, Maße).
- Ein Wert fehlt bei einem Leser, der andere hat ihn (Ergänzung, kein Widerspruch): wird übernommen, wenn die Summen danach stimmen und das Zitat wörtlich in der Quelle steht.
- Beide haben einen Wert, die Werte unterscheiden sich (echter Widerspruch): entscheidet nur der Beleg selbst. Genau eine Fassung hat in sich stimmige Summen (Positionen = Total, Stück = Gesamtstück, Raten = Total) -> sie gilt.
  Sonst bleibt der Fall offen (Mensch).
Immer: keine Bankdaten, Zitate wörtlich aus der Quelle. Maßtabellen/Spezifikationen werden nicht angefasst (measurements_p2 nutzt dort nur übereinstimmende Messpunkte)."""
import argparse
import copy
import glob
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import phase2_check as pc  # noqa: E402

P2 = ROOT / "output" / "phase2"
OUT = P2 / "B10"


EMPTY = (None, [], {}, "")
FIELD = {"order.total": ("order", "total"), "order.pieces": ("order", "pieces"), "order.items": ("order", "items")}


def has_totals(ex):
    o = ex.get("order") or {}
    return o.get("total") is not None and bool(o.get("items"))


def own_problems(ex, src_text):
    qe, _ = pc.check_quotes(ex, src_text)
    return qe + pc.check_sums(ex) + pc.check_composition(ex) + pc.check_bank(ex)


def resolve(L, P, text):
    """-> (fassung|None, begruendung)"""
    ca, cb = pc._canon(L), pc._canon(P)
    diffs = {k: (ca[k], cb[k]) for k in ca if ca[k] != cb[k]}
    if any(k.startswith("measurements") for k in diffs):
        return None, "Maßdaten weichen ab (nicht Teil dieser Schlichtung)"
    conflicts = [k for k, (x, y) in diffs.items() if x not in EMPTY and y not in EMPTY]
    sums_ok = lambda e: not pc.check_sums(e)
    if conflicts:
        okl, okp = sums_ok(L), sums_ok(P)
        if okl == okp:
            return None, "Widerspruch bei %s, Summen sprechen nicht eindeutig (Leser %s, Prüfer %s)" % (", ".join(conflicts), "stimmig" if okl else "unstimmig", "stimmig" if okp else "unstimmig")
        W, O, who = (copy.deepcopy(L), P, "Leser") if okl else (copy.deepcopy(P), L, "Prüfer")
        why = ["Widerspruch bei %s: %s-Summen stimmen mit dem Beleg, die andere Fassung nicht" % (", ".join(conflicts), who)]
    else:
        W, O = copy.deepcopy(L), P
        why = []
    gaps = [k for k, (x, y) in diffs.items() if k not in conflicts]
    for k in gaps:
        sec, fld = FIELD[k]
        if (W.get(sec) or {}).get(fld) in EMPTY and (O.get(sec) or {}).get(fld) not in EMPTY:
            W.setdefault(sec, {})[fld] = copy.deepcopy(O[sec][fld])
            for f in O.get("facts") or []:   # Stueckzahl ergibt sich aus den Positionen (Summenpruefung), braucht kein eigenes Zitat
                if k != "order.pieces" and (f.get("key") == k or str(f.get("key", "")).startswith(k + ".")):
                    W.setdefault("facts", []).append(f)
            why.append("%s aus der anderen Lesung ergänzt" % k)
    if own_problems(W, text):
        return None, "geschlichtete Fassung nicht stimmig: " + "; ".join(own_problems(W, text)[:2])
    return W, "; ".join(why) or "keine Kern-Abweichung"


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    rep = ["# STOPP schlichten (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), ""]
    resolved, open_, skipped, vendors = [], [], [], set()
    for sf in sorted(glob.glob(str(P2 / "*" / "STOPP.md"))):
        d = Path(sf).parent
        for m in re.finditer(r"^- (att_[0-9a-f]+) \((.*)\)$", Path(sf).read_text(), re.M):
            i, name = m.group(1), m.group(2)
            ef, cf, src = d / "extract" / (i + ".json"), d / "check" / (i + ".json"), d / "src" / (i + ".txt")
            if not (ef.exists() and cf.exists() and src.exists()):
                open_.append((d.name, i, name, "Extrakt/Prüf-Datei/Quelle fehlt")); continue
            L, P = json.loads(ef.read_text()), json.loads(cf.read_text())
            if not (has_totals(L) or has_totals(P)):
                skipped.append((d.name, i, name, "kein Beleg mit Summen (Maße/Spezifikation/Sonstiges)")); continue
            text = src.read_text()
            W, why = resolve(L, P, text)
            if W is None:
                open_.append((d.name, i, name, why)); continue
            resolved.append((d.name, i, name, why))
            vendors.add(d.name)
            if a.apply:
                (d / "stopp_orig").mkdir(exist_ok=True)
                shutil.copy(ef, d / "stopp_orig" / (i + ".leser.json")); shutil.copy(cf, d / "stopp_orig" / (i + ".pruefer.json"))
                ef.write_text(json.dumps(W, ensure_ascii=False, indent=1)); cf.write_text(json.dumps(W, ensure_ascii=False, indent=1))
    rep += ["Geschlichtet: %d | offen: %d | kein Summenbeleg (unverändert): %d" % (len(resolved), len(open_), len(skipped)), "", "## Geschlichtet (gültige Lesung übernommen)", ""]
    rep += ["- %s %s (%s): %s" % x for x in resolved]
    rep += ["", "## Offen (bleibt beim Menschen)", ""] + ["- %s %s (%s): %s" % x for x in open_]
    rep += ["", "## Nicht betroffen (keine Summen)", ""] + ["- %s %s (%s)" % x[:3] for x in skipped]
    rep += ["", "Betroffene Lieferanten: %s" % ", ".join(sorted(vendors))]
    (OUT / "stopp_resolve.md").write_text("\n".join(rep))
    (OUT / "stopp_vendors.json").write_text(json.dumps(sorted(vendors)))
    print("\n".join(rep[:3 + len(resolved) + 6]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
