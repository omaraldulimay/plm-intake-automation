"""Neue Produkte aus Plenty (Styles mit Einkaufsbestellung in den letzten 12 Monaten, die es im PLM noch nicht gibt), neu -> alt.

  python3 -m plm_intake.plenty_new [--n 25] [--since 2025-10-01]            TROCKENLAUF (Standard): Bericht output/plenty_new/plan_<Zeit>.md
  python3 -m plm_intake.plenty_new --apply [--n 25] [--since ...]           legt die Produkte per GraphQL createProduct an (Groessen, Lieferant, Collection/Kategorie, Kategorie-Code),
                                                                            liest per REST zurueck und schreibt die SKU-Liste nach output/plenty_new/created_<Zeit>.json
Danach (Farbvarianten, EAN/SKU, HS-Code): plm_intake/batch_chain.sh-Schritte mit --skus (siehe plm_intake/overnight.sh).
Regeln: nichts anlegen, wenn die SKU (ohne Sonderzeichen) im PLM schon vorkommt; Lieferant muss im PLM eindeutig gefunden werden (sonst uebersprungen und gemeldet);
Collection/Kategorie nur aus dem VORHANDENEN Bestand (kein Typ -> Uncategorized/General + Tag KATEGORIE-OFFEN); keine Bibliotheksfarben anlegen; nie loeschen/aendern."""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import barcodes as bc, core, daily, new_products as npd  # noqa: E402

OUT = ROOT / "output" / "plenty_new"
SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL", "5XL", "6XL"]
MAX_PER_RUN = 40
TAG = "plenty-import"


def alnum(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def size_key(z):
    u = str(z).upper().replace(" ", "")
    if u in SIZE_ORDER:
        return (0, SIZE_ORDER.index(u), u)
    m = re.match(r"^(\d+)", u)
    return (1, int(m.group(1)) if m else 999, u)


def clean_name(vname, style):
    n = re.sub(r"\s+-\s+" + re.escape(str(style)) + r"\s*$", "", str(vname or "").strip(), flags=re.I)
    return re.sub(r"\s+", " ", n).strip()


def plenty_candidates(since, limit):
    """Styles mit nicht stornierter Einkaufsbestellung seit `since`, neueste Bestellung zuerst (read-only psql)."""
    sql = """
with po as (select id, created_at from logistics.purchase_orders where cancelled_at is null and created_at >= '%s'),
hit as (select regexp_replace(upper(regexp_replace(s.variation_no,'-[A-Z]+[0-9]+$','')),'[^A-Z0-9]','','g') st, max(po.created_at)::date last_po
        from logistics.purchase_order_items i join po on po.id=i.purchase_order_id join logistics.skus s on s.ean=i.ean group by 1)
select h.st, h.last_po, regexp_replace(s.variation_no,'-[A-Z]+[0-9]+$','') style, coalesce(s.supplier_name,''), coalesce(s.variation_name,''), coalesce(s.attributes,''),
       coalesce(d.uvp::text,''), coalesce(d.purchase_price::text,'')
from hit h join logistics.skus s on regexp_replace(upper(regexp_replace(s.variation_no,'-[A-Z]+[0-9]+$','')),'[^A-Z0-9]','','g') = h.st
left join logistics.sku_details d on d.ean=s.ean and d.instance_key=s.instance_key
where s.variation_no ~ '-[A-Z]+[0-9]+$' order by h.last_po desc, h.st""" % since
    r = subprocess.run([bc.PSQL, bc.CONN, "-At", "-F", "\t", "-c", sql], capture_output=True, text=True, cwd=str(ROOT), timeout=600,
                       env=dict(__import__("os").environ, PGOPTIONS="-c default_transaction_read_only=on"))
    if r.returncode:
        raise RuntimeError("Plenty-Abfrage gescheitert: " + r.stderr[-200:])
    styles, order = {}, []
    for line in r.stdout.splitlines():
        st, last, style, sup, vname, attrs, uvp, ek = line.split("\t")
        e = styles.get(st)
        if e is None:
            e = styles[st] = {"key": st, "last_po": last, "style": style, "supplier": sup, "vname": vname, "colors": [], "sizes": [], "uvp": [], "ek": []}
            order.append(st)
        a = bc.parse_attrs(attrs)
        if a.get("color") and a["color"] not in e["colors"]:
            e["colors"].append(a["color"])
        if a.get("size") and a["size"] not in e["sizes"]:
            e["sizes"].append(a["size"])
        for lst, v in ((e["uvp"], uvp), (e["ek"], ek)):
            try:
                if v:
                    lst.append(float(v))
            except ValueError:
                pass
    return [styles[k] for k in order]


def build_spec(c, products, vendors, vendor_aliases, targets):
    """-> (spec, None) oder (None, Grund). targets: {(Collection, Kategorie): (collection_id, category_id)}."""
    sku = alnum(c["style"])
    if not sku:
        return None, "keine Stylenummer"
    v, why = core.match_vendor(c["supplier"], vendors, vendor_aliases) if c["supplier"] else (None, "kein Lieferant in Plenty")
    if not v:
        return None, "Lieferant nicht eindeutig im PLM: '%s' (%s)" % (c["supplier"], why)
    desc = clean_name(c["vname"], c["style"]) or c["style"]
    col, cat, code, sure = npd.resolve_target(desc, products)
    ids = targets.get((col, cat))
    if not ids:
        return None, "Collection/Kategorie '%s / %s' nicht im PLM" % (col, cat)
    sizes = sorted(c["sizes"], key=size_key) or ["ONE SIZE"]
    return {"sku": sku, "name": ("%s %s" % (c["style"], desc)).strip()[:120], "description": desc, "vendor_id": v["id"], "vendor": v["name"], "collection": col, "category": cat,
            "collection_id": ids[0], "category_id": ids[1], "category_code": code, "sizes": sizes, "colors": c["colors"], "last_po": c["last_po"],
            "tags": TAG + ("" if sure else ",KATEGORIE-OFFEN"), "uvp": max(c["uvp"]) if c["uvp"] else None, "purchase_price": max(c["ek"]) if c["ek"] else None}, None


def target_ids(products):
    out = {}
    for p in products:
        col, cat = p.get("collection") or {}, p.get("category") or {}
        if col.get("id") and cat.get("id"):
            out[(col.get("name"), cat.get("name"))] = (col["id"], cat["id"])
    return out


CREATE_JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v }); const V = n => ({ kind: 'Variable', name: N(n) });
  const F = (name, args, sel) => ({ kind: 'Field', name: N(name), arguments: args || [], selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const T = (n, list) => list ? { kind: 'ListType', type: { kind: 'NonNullType', type: { kind: 'NamedType', name: N(n) } } } : { kind: 'NamedType', name: N(n) };
  const vars = [['name', T('String')], ['sku', T('String')], ['description', T('String')], ['tags', T('String')], ['mainManufacturer', T('String')], ['customFields', T('JSON')],
                ['parent_collection', T('String')], ['category', T('String')], ['guid', { kind: 'NonNullType', type: T('String') }], ['isDefaultVariant', T('Boolean')], ['sizes', T('String', 1)]];
  const fields = ['name', 'sku', 'description', 'tags', 'mainManufacturer', 'customFields', 'parent_collection', 'category', 'guid', 'isDefaultVariant', 'sizes'].map(n => ({ kind: 'ObjectField', name: N(n), value: V(n) }));
  const doc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', variableDefinitions: vars.map(v => ({ kind: 'VariableDefinition', variable: V(v[0]), type: v[1] })),
    selectionSet: { kind: 'SelectionSet', selections: [F('createProduct', [{ kind: 'Argument', name: N('createProductInput'), value: { kind: 'ObjectValue', fields } }], [F('id'), F('sku'), F('name'), F('sizes', [], [F('id'), F('title')])])] } }] };
  const c = window.__APOLLO_CLIENT__; const out = [];
  for (const j of __JOBS__) {
    try { const r = await c.mutate({ mutation: doc, variables: j.vars, errorPolicy: 'all' });
          out.push({ sku: j.sku, id: r.data && r.data.createProduct && r.data.createProduct.id, err: (r.errors || []).map(e => e.message.slice(0, 200)) }); if (!(r.data && r.data.createProduct)) break; }
    catch (e) { out.push({ sku: j.sku, fatal: String(e.message).slice(0, 200) }); break; }   // bei Fehler sofort stoppen
  }
  return out;
})()'''


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25); ap.add_argument("--since", default=(dt.date.today() - dt.timedelta(days=365)).isoformat()); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    vendors = fetch_all(plm_client.call, "vendors"); products = fetch_all(plm_client.call, "products")
    have = {alnum(p.get("sku")) for p in products if p.get("sku")}
    aliases = json.load(open(daily.INTAKE / "vendor_aliases.json")) if (daily.INTAKE / "vendor_aliases.json").exists() else {}
    targets = target_ids(products)
    cands = [c for c in plenty_candidates(a.since, 100000) if alnum(c["style"]) not in have]
    specs, skipped = [], []
    for c in cands:
        s, why = build_spec(c, products, vendors, aliases, targets)
        (specs.append(s) if s else skipped.append((c["style"], c["supplier"], why)))
        if len(specs) >= min(a.n, MAX_PER_RUN):
            break
    rep = ["# Neue Produkte aus Plenty (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "", "Stand %s | Bestellungen seit %s | Kandidaten nicht im PLM: %d | dieser Batch: %d" % (
        dt.datetime.now().strftime("%Y-%m-%d %H:%M"), a.since, len(cands), len(specs)), ""]
    rep += ["| SKU | Name | Lieferant | Collection / Kategorie | Groessen | Farben | letzte Bestellung |", "|---|---|---|---|---|---|---|"]
    rep += ["| %s | %s | %s | %s / %s | %s | %d | %s |" % (s["sku"], s["name"][:32], s["vendor"][:22], s["collection"], s["category"][:14], ",".join(s["sizes"]), len(s["colors"]), s["last_po"]) for s in specs]
    import collections
    why = collections.Counter(re.sub(r"'.*?'", "'..'", w)[:70] for _, _, w in skipped)
    rep += ["", "## Uebersprungen bis zu diesem Batch: %d" % len(skipped)] + ["- %s: %d" % (w, n) for w, n in why.most_common(8)]
    OUT.mkdir(parents=True, exist_ok=True); stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if a.apply and specs:
        jobs = [{"sku": s["sku"], "vars": {"name": s["name"], "sku": s["sku"], "description": s["description"], "tags": s["tags"], "mainManufacturer": s["vendor_id"],
                                           "customFields": {npd.KATCODE_KEY: s["category_code"]} if s["category_code"] else {}, "parent_collection": s["collection_id"], "category": s["category_id"],
                                           "guid": str(uuid.uuid4()), "isDefaultVariant": False, "sizes": s["sizes"]}} for s in specs]
        res = bc.run_js(CREATE_JS.replace("__JOBS__", json.dumps(jobs)))
        rep += ["", "## Anlage"] + ["- %s: %s" % (r.get("sku"), r.get("id") or r.get("fatal") or r.get("err")) for r in res]
        created = [r["sku"] for r in res if r.get("id")]
        import time
        time.sleep(3)
        now = {alnum(p.get("sku")): p for p in fetch_all(plm_client.call, "products")}
        bad = []
        for s in specs:
            if s["sku"] not in created:
                continue
            p = now.get(s["sku"])
            if not p or [str(x.get("title") if isinstance(x, dict) else x) for x in (p.get("sizes") or [])] != s["sizes"] or (p.get("mainManufacturer") or {}).get("id") != s["vendor_id"] \
                    or (p.get("collection") or {}).get("id") != s["collection_id"] or (p.get("category") or {}).get("id") != s["category_id"]:
                bad.append(s["sku"])
        rep += ["", "## Rueckpruefung", "- %s" % ("ALLES zurueckgelesen und gleich (%d Produkte)" % len(created) if not bad and len(created) == len(specs) else "ABWEICHUNG/FEHLT: %s (angelegt %d von %d)" % (bad, len(created), len(specs)))]
        (OUT / ("created_%s.json" % stamp)).write_text(json.dumps(created))
        (OUT / "last_created.json").write_text(json.dumps(created))
        # Kategorie-Code/UVP/EK per REST (customFields werden vom PUT ersetzt: zusammenfuehren)
        for s in specs:
            p = now.get(s["sku"])
            if p and s["sku"] in created:
                body = npd.field_patch(s, p)
                if body:
                    plm_client.call("PUT", "products/" + p["id"], body)
    (OUT / ("plan_%s.md" % stamp)).write_text("\n".join(rep))
    print("\n".join(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
