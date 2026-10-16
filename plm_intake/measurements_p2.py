"""Phase 2: Maßtabellen aus geprüften Extrakten ins PLM (importProductMeasurements). Trockenlauf Standard.

  python3 -m plm_intake.measurements_p2 output/phase2/<lieferant> [--apply]

Nur Messpunkte, die Leser (extract/) UND Prüf-Agent (check/) gleich gelesen haben; Toleranzzeilen nicht.
Nur Produkte OHNE Maße (B0-Inventur + frische Rücklesung), nur Größen, die das Produkt hat (XXL = 2XL).
Neueste Quelle je Produkt. Nach --apply: Rücklesung productMeasurementMetadata. Bericht measurements_plan.md / measurements_result.json."""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BROWSER = ROOT / "plm_intake" / "browser"
SIZE_ALIAS = {"XXL": "2XL", "2XL": "XXL", "XXXL": "3XL", "3XL": "XXXL"}

IMPORT_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v });
  const T = n => ({ kind: 'NamedType', name: N(n) });
  const doc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', name: N('importProductMeasurements'),
    variableDefinitions: [{ kind: 'VariableDefinition', variable: { kind: 'Variable', name: N('input') },
      type: { kind: 'NonNullType', type: { kind: 'ListType', type: { kind: 'NonNullType', type: T('ImportProductMeasurementRowInput') } } } }],
    selectionSet: { kind: 'SelectionSet', selections: [{ kind: 'Field', name: N('importProductMeasurements'),
      arguments: [{ kind: 'Argument', name: N('input'), value: { kind: 'Variable', name: N('input') } }],
      selectionSet: { kind: 'SelectionSet', selections: ['productsMatched', 'productsMissing', 'itemsAdded'].map(f => ({ kind: 'Field', name: N(f) })) } }] } }] };
  const c = window.__APOLLO_CLIENT__; const out = [];
  for (const batch of __BATCHES__) {
    try { const r = await c.mutate({ mutation: doc, variables: { input: batch }, errorPolicy: 'all' });
          out.push({ n: batch.length, data: r.data && r.data.importProductMeasurements, err: r.errors && r.errors.length ? r.errors[0].message.slice(0, 200) : null }); }
    catch (e) { out.push({ n: batch.length, err: String(e.message).slice(0, 200) }); }
  }
  return out;
})()'''


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def rows_of(x):
    m = x.get("measurements") or {}
    out = {}
    for r in m.get("rows") or []:
        name = str(r.get("name") or "").strip()
        vals = {str(k): float(v) for k, v in (r.get("values") or {}).items() if v not in (None, "")}
        if name and vals and not name.lower().startswith("toleranz"):
            out[name] = vals
    return out


def agreed_rows(ex, ck):
    """Leser-Zeilen, deren Werte-Satz der Prüf-Agent identisch hat (Namen dürfen abweichen)."""
    theirs = {tuple(sorted(v.items())) for v in rows_of(ck).values()}
    return {n: v for n, v in rows_of(ex).items() if tuple(sorted(v.items())) in theirs}


IAN_ALIAS = {"SLM26001": "561872", "SLM26002": "561876", "SLM26003": "561878", "SLM26004": "561879"}  # Dateinamen "TP_Spec of IAN# 561872 - SLM26-001"


def find_product(style, name, products):
    style = IAN_ALIAS.get(norm(style), style)
    keys = [norm(style), norm(re.sub(r"-\d$", "", str(style or ""))), norm(name)]
    by_sku = {}
    for p in products:
        for k in (norm(p.get("sku")), norm(p.get("name"))):
            if k and p not in by_sku.setdefault(k, []):
                by_sku[k].append(p)
    for k in keys:
        if k and len(by_sku.get(k, [])) == 1:
            return by_sku[k][0]
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    d = Path(a.dir).resolve()
    inv = json.loads((ROOT / "output/phase2/B0/inventur.json").read_text())["rows"]
    src = {s["id"]: s for s in json.loads((d / "sources.json").read_text())}
    cands = []
    for ef in sorted((d / "extract").glob("*.json")):
        cf = d / "check" / ef.name
        if not cf.exists():
            continue
        ex, ck = json.loads(ef.read_text()), json.loads(cf.read_text())
        rows = agreed_rows(ex, ck)
        if not rows:
            continue
        pr = ex.get("product") or {}
        cands.append({"file": ef.stem, "datum": src.get(ef.stem, {}).get("datum", ""), "style": pr.get("style"), "name": pr.get("name"),
                      "rows": rows, "n_leser": len(rows_of(ex))})
    from plm_intake import batch_plan as bp
    if 'meta:' not in bp.DETAIL_JS:
        bp.DETAIL_JS = bp.DETAIL_JS.replace("    ident:", "    meta: '{ productMeasurementMetadata(productId:$productId){ id metadata } }',\n    ident:")
    plan, skip, best = [], [], {}
    for c in cands:
        p = find_product(c["style"], None, inv)
        if not p:
            skip.append((c, "kein eindeutiges Produkt im PLM"))
            continue
        if p.get("masse"):
            skip.append((c, "Produkt %s hat schon Maße (nur leere Felder)" % p["sku"]))
            continue
        if p["id"] not in best or c["datum"] > best[p["id"]][0]["datum"]:
            if p["id"] in best:
                skip.append((best[p["id"]][0], "ältere Quelle für %s" % p["sku"]))
            best[p["id"]] = (c, p)
        else:
            skip.append((c, "ältere Quelle für %s" % p["sku"]))
    det = bp.fetch_details(list(best)) if best else {}
    for pid, (c, p) in best.items():
        info = (det.get(pid) or {}).get("info") or {}
        if (det.get(pid) or {}).get("meta") and any((m.get("metadata") or {}) for m in det[pid]["meta"]):
            skip.append((c, "Produkt %s hat laut Rücklesung schon Messzeilen" % p["sku"]))
            continue
        sizes = [z["title"] for z in info.get("sizes") or []]
        lines = []
        for pom, vals in c["rows"].items():
            for sz, v in vals.items():
                t = sz if sz in sizes else SIZE_ALIAS.get(sz) if SIZE_ALIAS.get(sz) in sizes else None
                if t:
                    lines.append({"productSku": p["sku"], "productName": info.get("name") or p["name"], "pom": pom, "size": t, "value": ("%g" % v), "unit": "cm"})
        if not lines:
            skip.append((c, "keine Größe passt (Produkt: %s)" % ",".join(sizes)))
            continue
        plan.append({"product_id": pid, "sku": p["sku"], "file": c["file"], "datum": c["datum"], "poms": len(c["rows"]), "poms_leser": c["n_leser"], "lines": lines})
    L = ["# Maß-Import %s (%s)" % (d.name, "APPLY" if a.apply else "TROCKENLAUF"), "", "## Plan (%d Produkte, %d Zeilen)" % (len(plan), sum(len(x["lines"]) for x in plan)), ""]
    L += ["- %s <- %s (%s): %d Messpunkte gleich gelesen (Leser %d), %d Zeilen" % (x["sku"], x["file"], x["datum"], x["poms"], x["poms_leser"], len(x["lines"])) for x in plan]
    L += ["", "## Nicht importiert", ""] + ["- %s (%s): %s" % (c["file"], c.get("style"), why) for c, why in skip]
    res = {"plan": plan}
    if a.apply and plan:
        batches = [x["lines"] for x in plan]
        js = IMPORT_JS.replace("__BATCHES__", json.dumps(batches, ensure_ascii=False))
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(js)
        r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(BROWSER), timeout=900)
        res["import"] = json.loads(r.stdout) if r.returncode == 0 else {"fehler": r.stderr[-500:]}
        back = bp.fetch_details([x["product_id"] for x in plan])
        L += ["", "## Rücklesung", ""]
        for x in plan:
            n = len([m for m in (back.get(x["product_id"]) or {}).get("meta") or [] if m.get("metadata")])
            L.append("- %s: %d Messzeilen im PLM (geplant %d Messpunkte) %s" % (x["sku"], n, x["poms"], "OK" if n >= x["poms"] else "ABWEICHUNG"))
        res["back"] = {x["sku"]: (back.get(x["product_id"]) or {}).get("meta") for x in plan}
    (d / "measurements_plan.md").write_text("\n".join(L))
    (d / "measurements_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("\n".join(L))


if __name__ == "__main__":
    main()
