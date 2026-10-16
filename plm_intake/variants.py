"""Fehlende Farbvarianten ins PLM (damit EAN/SKU aus Plenty ein Ziel haben).

  python3 -m plm_intake.variants [--n 25] [--skus A,B]           TROCKENLAUF (Standard): Plan + Bericht output/variants/plan_<Zeit>.md
  python3 -m plm_intake.variants --apply [--n 25] [--skus A,B]   legt fehlende Farbvarianten an, verknuepft die Bibliotheksfarbe und liest zurueck

Eine Farbe gilt als fehlend, wenn Plenty sie fuer das Produkt kennt, das PLM aber KEINE Zelle dieser Farbe hat. Name der Variante = Plenty-Farbname.
Verknuepft wird nur mit einer Bibliotheksfarbe MIT Hex (ohne Hex stuerzt die Produktabfrage der App serverseitig ab) und nur bei eindeutigem Namenstreffer.
Fehlt am Produkt eine Groesse (z. B. 3XL), wird sie NICHT angelegt (Groessen sind an bestehenden Produkten nicht aenderbar) und steht im Bericht.
Nie loeschen, nie umbenennen, keine Dubletten (Variantenname schon da -> nichts tun). Danach: python3 -m plm_intake.barcodes --apply schreibt die EANs."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import barcodes as bc, core  # noqa: E402

OUT = ROOT / "output" / "variants"
MAX_VARIANTS_PER_RUN = int(__import__("os").environ.get("PLM_MAX_VARIANTS", 40))   # Standard 40; der Nachtlauf fuer neue Plenty-Styles (viele Farben je Style) setzt PLM_MAX_VARIANTS hoeher

COLORS_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v });
  const F = (name, args, sel) => ({ kind: 'Field', name: N(name), arguments: (args || []).map(a => ({ kind: 'Argument', name: N(a[0]), value: a[1] })), selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const V = n => ({ kind: 'Variable', name: N(n) });
  const T = n => ({ kind: 'NamedType', name: N(n) });
  const q = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', variableDefinitions: [{ kind: 'VariableDefinition', variable: V('search'), type: T('String') }, { kind: 'VariableDefinition', variable: V('after'), type: T('Int') }, { kind: 'VariableDefinition', variable: V('limit'), type: T('Int') }],
    selectionSet: { kind: 'SelectionSet', selections: [F('getAllTypeColorsCombined', [['search', V('search')], ['after', V('after')], ['limit', V('limit')]], [F('colors', [], [F('id'), F('name'), F('colorType'), F('hex'), F('code')])])] } }] };
  const c = window.__APOLLO_CLIENT__; const out = {};
  for (const name of __NAMES__) {
    try { const r = await c.query({ query: q, variables: { search: name, after: 0, limit: 40 }, fetchPolicy: 'no-cache', errorPolicy: 'all' });
          out[name] = ((r.data && r.data.getAllTypeColorsCombined && r.data.getAllTypeColorsCombined.colors) || []).map(x => ({ id: x.id, name: x.name, colorType: x.colorType, hex: x.hex, code: x.code })); }
    catch (e) { out[name] = { err: String(e.message).slice(0, 120) }; }
  }
  return out;
})()'''

WRITE_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v });
  const F = (name, args, sel) => ({ kind: 'Field', name: N(name), arguments: (args || []).map(a => ({ kind: 'Argument', name: N(a[0]), value: a[1] })), selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const V = n => ({ kind: 'Variable', name: N(n) });
  const NN = n => ({ kind: 'NonNullType', type: { kind: 'NamedType', name: N(n) } });
  const mk = (op, vars, sel) => ({ kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', variableDefinitions: vars.map(v => ({ kind: 'VariableDefinition', variable: V(v[0]), type: NN(v[1]) })), selectionSet: { kind: 'SelectionSet', selections: [sel] } }] });
  const create = mk('c', [['productId', 'String'], ['input', 'CreateProductVariantInput']], F('createProductVariant', [['productId', V('productId')], ['input', V('input')]], [F('id'), F('name'), F('colorId')]));
  const update = mk('u', [['productId', 'String'], ['variantId', 'String'], ['input', 'UpdateProductVariantInput']], F('updateProductVariant', [['productId', V('productId')], ['variantId', V('variantId')], ['input', V('input')]], [F('id'), F('name'), F('colorId')]));
  const c = window.__APOLLO_CLIENT__; const out = [];
  for (const j of __JOBS__) {
    try {
      const r1 = await c.mutate({ mutation: create, variables: { productId: j.productId, input: { name: j.name } }, errorPolicy: 'all' });
      const v = r1.data && r1.data.createProductVariant;
      if (!v) { out.push({ sku: j.sku, name: j.name, err: (r1.errors || []).map(e => e.message.slice(0, 160)) }); break; }
      let linked = null;
      if (j.colorId) { const r2 = await c.mutate({ mutation: update, variables: { productId: j.productId, variantId: v.id, input: { name: j.name, colorId: j.colorId, colorType: j.colorType } }, errorPolicy: 'all' });
                       linked = r2.data && r2.data.updateProductVariant ? r2.data.updateProductVariant.colorId : ('Link-Fehler: ' + (r2.errors || []).map(e => e.message.slice(0, 120)).join('; ')); }
      out.push({ sku: j.sku, name: j.name, variantId: v.id, linked });
    } catch (e) { out.push({ sku: j.sku, name: j.name, fatal: String(e.message).slice(0, 200) }); break; }
  }
  return out;
})()'''


def pick_color(options, wanted):
    """Eindeutige Bibliotheksfarbe MIT Hex zum Plenty-Farbnamen, sonst None (+ Grund)."""
    if not isinstance(options, list):
        return None, "Farbsuche fehlgeschlagen"
    exact = [o for o in options if core.norm_color(o.get("name")) == core.norm_color(wanted) and core.norm_color(wanted)]
    with_hex = [o for o in exact if o.get("hex")]
    if len(with_hex) == 1:
        return with_hex[0], ""
    if len(with_hex) > 1:
        return None, "%d Bibliotheksfarben mit Hex heissen so" % len(with_hex)
    if exact:
        return None, "Bibliotheksfarbe ohne Hex (Verknuepfung wuerde die App-Abfrage zum Absturz bringen)"
    return None, "keine Bibliotheksfarbe mit diesem Namen"


def plan_variants(plan_missing, cells, product_sizes):
    """plan_missing: Eintraege aus barcodes.plan_product()['missing'] (variation_no, color, size, grund). -> (neue Farben, blockierte Groessen)."""
    have = set()
    for c in cells:
        have |= {bc.colour_key(c.get("variant")), bc.colour_key(c.get("color"))}
    have.discard(("?", "", ()))
    sizes_ok = {bc.norm_size(x) for x in product_sizes}
    colors, blocked = {}, []
    for vn, color, size, why in plan_missing:
        if why != "keine Zelle":
            continue
        if not str(color or "").strip():   # Plenty ohne Farbangabe: nie eine namenlose Variante anlegen
            continue
        cn = bc.colour_key(color)
        if cn in have:
            blocked.append((vn, color, size, "Farbe vorhanden, aber Groesse fehlt am Produkt"))
            continue
        colors.setdefault(color, set()).add(bc.norm_size(size))
    new = []
    for color, sz in sorted(colors.items()):
        missing_sizes = sorted(s for s in sz if s not in sizes_ok)
        new.append({"name": color, "sizes": sorted(sz), "missing_sizes": missing_sizes})
    return new, blocked


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25); ap.add_argument("--skus"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true"); ap.add_argument("--offset", type=int, default=0)
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    vendors = fetch_all(plm_client.call, "vendors"); products = fetch_all(plm_client.call, "products")
    prods = bc.select_products(a.n, a.skus, vendors, products, a.all, a.offset)
    ident = bc.run_js(bc.READ_JS.replace("__IDS__", json.dumps([p["id"] for p in prods])))
    prows = bc.plenty_rows([p.get("sku") for p in prods])
    plans = []
    for p in prods:
        cells = bc.cells_of(ident.get(p["id"]))
        pl = bc.plan_product(prows.get(core.norm(p.get("sku")), []), cells, {})
        sizes = [s.get("title") if isinstance(s, dict) else s for s in (p.get("sizes") or [])] or sorted({c["size"] for c in cells})
        new, blocked = plan_variants(pl["missing"], cells, sizes)
        if new or blocked:
            plans.append({"p": p, "new": new, "blocked": blocked})
    names = sorted({v["name"] for x in plans for v in x["new"]})
    lib = bc.run_js(COLORS_JS.replace("__NAMES__", json.dumps(names))) if names else {}
    report = ["# Variantenplan (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "", "Stand %s, %d Produkte" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M"), len(prods)), ""]
    jobs = []
    for x in plans:
        p = x["p"]
        report.append("## %s %s" % (p.get("sku"), str(p.get("name"))[:36]))
        for v in x["new"]:
            col, why = pick_color(lib.get(v["name"]), v["name"])
            line = "- NEUE VARIANTE %s: Groessen %s" % (v["name"], ", ".join(v["sizes"]))
            line += " | Bibliotheksfarbe: %s" % ("%s (%s, %s)" % (col["name"], col["hex"], col["colorType"]) if col else "keine Verknuepfung (%s)" % why)
            if v["missing_sizes"]:
                line += " | Groesse(n) fehlen am Produkt: %s" % ", ".join(v["missing_sizes"])
            report.append(line)
            jobs.append({"productId": p["id"], "sku": p.get("sku"), "name": v["name"], "colorId": col["id"] if col else None, "colorType": col["colorType"] if col else None})
        for b in x["blocked"][:6]:
            report.append("- BLOCKIERT %s (%s / %s): %s" % b)
    report += ["", "Gesamt neue Varianten: %d (Limit %d pro Lauf)" % (len(jobs), MAX_VARIANTS_PER_RUN)]
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if a.apply:
        if len(jobs) > MAX_VARIANTS_PER_RUN:
            report.append("ABBRUCH: mehr als %d Varianten in einem Lauf." % MAX_VARIANTS_PER_RUN)
        else:
            res = bc.run_js(WRITE_JS.replace("__JOBS__", json.dumps(jobs)))
            report += ["", "## Schreibergebnis"] + ["- %s %s: %s" % (r.get("sku"), r.get("name"), json.dumps({k: v for k, v in r.items() if k not in ("sku", "name")}, ensure_ascii=False)) for r in res]
            after = bc.run_js(bc.READ_JS.replace("__IDS__", json.dumps(sorted({j["productId"] for j in jobs}))))
            missing = []
            for j in jobs:
                have = {c["variant"] for c in bc.cells_of(after.get(j["productId"]))}
                if j["name"] not in have:
                    missing.append((j["sku"], j["name"]))
            report += ["", "## Rueckpruefung", "- %s" % ("alle Varianten sind jetzt im PLM" if not missing else "FEHLT: %s" % missing)]
    (OUT / ("plan_%s.md" % stamp)).write_text("\n".join(report))
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
