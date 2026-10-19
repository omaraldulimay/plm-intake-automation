"""Phase 2: Verpackung (Karton L/B/H, Brutto je Karton, Stueck je Karton) aus geprueften Extrakten ans Produkt. Trockenlauf Standard.

  python3 -m plm_intake.packaging_p2 [--apply]

Nur Werte, die Leser (extract/) UND Pruef-Agent (check/) gleich gelesen haben; nur LEERE Verpackungsfelder (vorhandene, z. B. HS-Code, bleiben).
Produkt per Style/IAN eindeutig. Neueste Quelle je Produkt. Schreiben mit packaging.WRITE_JS, danach Ruecklesung.
Bericht output/phase2/packaging_plan.md"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
P2 = ROOT / "output" / "phase2"
MAP = {"carton_l_cm": "cartonLengthCm", "carton_b_cm": "cartonWidthCm", "carton_h_cm": "cartonHeightCm", "gross_kg": "cartonGrossWeightKg", "pcs_per_carton": "piecesPerCarton"}


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def pk(x):
    p = x.get("packaging")
    if isinstance(p, list):
        p = p[0] if len(p) == 1 else None
    if not isinstance(p, dict):
        return {}
    return {MAP[k]: float(v) for k, v in (p or {}).items() if k in MAP and isinstance(v, (int, float)) and v > 0}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    from plm_intake import batch_plan, packaging
    from plm_intake.barcodes import run_js
    inv = json.loads((ROOT / "output/phase2/B0/inventur.json").read_text())["rows"]
    by = {}
    for p in inv:
        for k in {norm(p["sku"]), norm(p["name"]).split("MEN")[0] if p.get("name") else ""}:
            if k:
                by.setdefault(k, []).append(p)
    cand, skip = {}, []
    for ef in sorted(P2.glob("*/extract/*.json")):
        cf = ef.parent.parent / "check" / ef.name
        ex = json.loads(ef.read_text())
        a1 = pk(ex)
        if not a1:
            continue
        a2 = pk(json.loads(cf.read_text())) if cf.exists() else {}
        same = {k: v for k, v in a1.items() if k in a2 and abs(a2[k] - v) < 0.01}
        style = (ex.get("product") or {}).get("style") or ""
        ian = re.search(r"\b(5618\d\d)", json.dumps(ex.get("product") or {}) + ef.read_text()[:3000])
        key = norm(ian.group(1)) if ian else norm(style)
        hits = {p["id"]: p for p in by.get(key, [])}
        if not same:
            skip.append("%s/%s (%s): kein von beiden gleich gelesener Wert" % (ef.parent.parent.name, ef.stem, style or key))
            continue
        if len(hits) != 1:
            skip.append("%s/%s (%s): Produkt nicht eindeutig (%d Treffer)" % (ef.parent.parent.name, ef.stem, key, len(hits)))
            continue
        pid = next(iter(hits))
        src = json.loads((ef.parent.parent / "sources.json").read_text()) if (ef.parent.parent / "sources.json").exists() else []
        datum = next((s.get("datum") for s in src if s["id"] == ef.stem), "")
        if pid not in cand or datum > cand[pid]["datum"]:
            cand[pid] = {"id": pid, "sku": hits[pid]["sku"], "werte": same, "datum": datum, "quelle": "%s/%s" % (ef.parent.parent.name, ef.stem)}
    det = batch_plan.fetch_details(list(cand)) if cand else {}
    jobs, L = [], ["# Verpackung aus Belegen (%s)" % ("APPLY" if a.apply else "TROCKENLAUF"), ""]
    for pid, c in cand.items():
        cur = ((det.get(pid) or {}).get("info") or {}).get("packaging") or {}
        new = {k: v for k, v in c["werte"].items() if cur.get(k) in (None, "", 0)}
        if not new:
            L.append("- %s: schon befuellt, nichts zu tun" % c["sku"])
            continue
        merged = {k: cur.get(k) for k in packaging.PKG_KEYS if cur.get(k) not in (None, "")}
        merged.update({k: (int(v) if k == "piecesPerCarton" else v) for k, v in new.items()})
        jobs.append({"id": pid, "sku": c["sku"], "packaging": merged})
        L.append("- %s <- %s (%s): %s" % (c["sku"], c["quelle"], c["datum"], new))
    L += ["", "## Nicht geschrieben", ""] + ["- " + s for s in skip]
    if a.apply and jobs:
        res = run_js(packaging.WRITE_JS.replace("__JOBS__", json.dumps(jobs)))
        after = batch_plan.fetch_details([j["id"] for j in jobs])
        bad = [j["sku"] for j in jobs if any(((after.get(j["id"]) or {}).get("info") or {}).get("packaging", {}).get(k) != v for k, v in j["packaging"].items())]
        L += ["", "## Ruecklesung", "- Fehler beim Schreiben: %s" % [r for r in res if r.get("err") or r.get("fatal")], "- %s" % ("alles gleich" if not bad else "ABWEICHUNG: %s" % bad)]
    (P2 / "packaging_plan.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
