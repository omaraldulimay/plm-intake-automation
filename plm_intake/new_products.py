"""Neue Produkte aus Lieferanten-Dokumenten anlegen (nur wenn die Bestellung automatisch angelegt wird).

Regeln (Omar, 15.10.): Die Lieferanten-Styles sind NEU, Smilodox-SKUs/EANs gibt es noch nicht. Das Produkt bekommt deshalb die Lieferanten-Stylenummer als
VORLAEUFIGE SKU, Tags "SKU-OFFEN" und "aus-mail". Einsortiert wird in die BESTEHENDE Struktur: Collection = Produkttyp (Hoodie, Hosen, Outerwear ...), Kategorie = codierter Typ
("HOO - Hoodie / Kapuzenpullover"), dazu das Feld Kategorie-Code. Collection/Kategorie werden aus den vorhandenen Produkten gelesen, NIE neu erfunden; ohne sicheren Typ: Uncategorized/General + Tag KATEGORIE-OFFEN.
Eigene SKU/EAN vergibt ein Mensch spaeter im PLM.
Nichts wird angelegt, wenn es das Produkt (oder seinen Basisstyle) schon gibt: dann bleibt die Position ohne Link bzw. der Fall beim Menschen.
Ablauf: Farben (GraphQL addLibraryColor, nur wenn Name fehlt) -> CSV-Import mit Groessen/Varianten/Lieferant -> Farb-Link (updateProductVariantFn).
"""
import csv
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import core  # noqa: E402

BROWSER = ROOT / "plm_intake" / "browser"
MAX_NEW_PER_RUN = 8
# Produkttyp -> Kategorie-Code (so heissen die vorhandenen Kategorien: "HOO – Hoodie / Kapuzenpullover"); Reihenfolge = Prioritaet
TYPE_CODES = [("JMP", r"jumpsuit|overall|tulum"), ("JAC", r"jacket|jacke|ceket|parka|windbreaker|anorak|coat|\bmont\b|vest\b|weste"), ("HOO", r"hood|kapuz"),
              ("SWE", r"sweat(?!\s*pant)(?!pant)|pullover|crewneck|kazak"), ("JOG", r"jogg|sweat\s*pant|sweatpant|trainingshose|tracksuit bottom|esofman|eşofman"),
              ("PNT", r"\bpants?\b|trouser|hose\b|chino|cargo"), ("SHO", r"shorts?\b|sort\b"), ("LEG", r"legging|tayt|tights?\b"), ("POL", r"polo"), ("LSL", r"long\s*sleeve|longsleeve|langarm"),
              ("TNK", r"tank|stringer|atlet"), ("CRP", r"crop"), ("TEE", r"t-?shirt|\btee\b|tisort|tişört|shirt"), ("BRA", r"\bbra\b|bralette|bustier|sport-bh|sport bh|\bbh\b"),
              ("BAG", r"\bbag\b|tasche|backpack|rucksack|duffel"), ("CAP", r"\bcap\b|beanie|\bhat\b|bucket|muetze|mütze"), ("SOC", r"sock|socken"), ("BOX", r"boxer"),
              ("SNK", r"sneaker|shoe|schuh|boot|ayakkab"), ("DRK", r"\bbottles?\b|\bmug\b|\bcups?\b|tumbler|shaker|flasche|becher")]
FALLBACK = ("Uncategorized", "General")
EXTRA_TAGS = "aus-mail,SKU-OFFEN"


def guess_code(name):
    n = str(name or "").lower()
    for code, pat in TYPE_CODES:
        if re.search(pat, n):
            return code
    return None


def known_targets(products):
    """{Kategorie-Code: (Collection, Kategorie)} aus den VORHANDENEN Produkten (haeufigstes Paar je Code)."""
    import collections
    cnt = collections.defaultdict(collections.Counter)
    for p in products:
        col, cat = (p.get("collection") or {}).get("name"), (p.get("category") or {}).get("name")
        m = re.match(r"\s*([A-Z]{3})\b", str(cat or ""))
        if col and cat and m:
            cnt[m.group(1)][(col, cat)] += 1
    return {code: c.most_common(1)[0][0] for code, c in cnt.items()}


def resolve_target(name, products):
    """(Collection, Kategorie, Code, sicher?) -> nur bestehende Namen; unbekannter Typ -> Uncategorized/General."""
    code = guess_code(name)
    tgt = known_targets(products).get(code) if code else None
    if tgt:
        return tgt[0], tgt[1], code, True
    return FALLBACK[0], FALLBACK[1], None, False


def base_style(sku):
    """'HY29582-Z-A' -> 'hy29582' (Basisstyle: Buchstaben+Ziffern am Anfang)."""
    m = re.match(r"\s*([A-Za-z]{1,6}\d{3,})", str(sku or ""))
    return core.norm(m.group(1)) if m else core.norm(sku)


def existing_style_hit(sku, products, style_aliases=None):
    """Gibt es das Produkt (oder den Basisstyle) schon? -> ('exakt'|'basis'|'alias', produkt) oder None. Ein Basis-Treffer heisst: Variante eines vorhandenen Styles, Mensch entscheidet."""
    n = core.norm(sku)
    if not n:
        return None
    alias = (style_aliases or {}).get(sku) or (style_aliases or {}).get(n)
    for p in products:
        ps = core.norm(p.get("sku"))
        if alias and (p.get("id") == alias or ps == core.norm(alias)):
            return "alias", p
        if ps and ps == n:
            return "exakt", p
        if n in core.norm(p.get("name")) and len(n) >= 5:
            return "exakt", p
    b = base_style(sku)
    if len(b) >= 5 and b != n:
        for p in products:
            ps = core.norm(p.get("sku"))
            if ps and (ps == b or base_style(p.get("sku")) == b):
                return "basis", p
    return None


def plan_products(po, vendor, products, style_aliases=None, limit=MAX_NEW_PER_RUN):
    """-> (specs, skipped): specs = anzulegende Produkte, skipped = [(sku, Grund)] (Mensch / ohne Link)."""
    specs, skipped, seen = [], [], set()
    for it in po.get("items") or []:
        sku = str(it.get("sku") or "").strip()
        if not sku:
            skipped.append(("?", "Position ohne Stylenummer: bleibt ohne Produktlink")); continue
        if core.norm(sku) in seen:
            continue
        seen.add(core.norm(sku))
        hit = existing_style_hit(sku, products, style_aliases)
        if hit:
            if hit[0] == "basis":
                skipped.append((sku, "Variante des vorhandenen Styles %s: Mensch entscheidet (neues Produkt oder gleiches?)" % hit[1].get("sku")))
            continue
        sizes, colors = [], []
        for v in it.get("variants") or []:
            if v.get("color") and v["color"] not in colors:
                colors.append(v["color"])
            for k in (v.get("sizes") or {}):
                if k not in sizes:
                    sizes.append(k)
        pi = it.get("product_info") or {}
        name = re.sub(r"\s+", " ", str(it.get("name") or "")).strip()
        col, cat, code, sure = resolve_target(name, products)
        specs.append({"sku": sku, "name": ("%s %s" % (sku, name)).strip()[:120], "description": name, "collection": col, "category": cat, "category_code": code, "sizes": sizes or ["ONE SIZE"],
                      "colors": colors, "vendor": vendor["name"], "year": str(pi.get("year") or ""), "barcode": pi.get("barcode") if core.valid_ean(pi.get("barcode")) else None,
                      "uvp": pi.get("uvp"), "purchase_price": pi.get("purchase_price"), "tags": EXTRA_TAGS + ("" if sure else ",KATEGORIE-OFFEN")})
    if len(specs) > limit:
        skipped += [(s["sku"], "mehr als %d neue Produkte in einem Lauf: Mensch bestaetigt" % limit) for s in specs[limit:]]
        specs = specs[:limit]
    return specs, skipped


def write_csv(specs, path):
    cols = ["Name", "Collection", "Category", "Status", "SKU", "Description", "Season", "Year", "Measurement Unit", "Sizes", "Variants", "Main Vendor", "Main Material", "Tags"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols)
        for s in specs:
            w.writerow([s["name"], s["collection"], s["category"], "", s["sku"], s["description"], "", s["year"], "cm", ", ".join(s["sizes"]), ", ".join(s["colors"]), s["vendor"], "", s["tags"]])


COLOR_JS = r"""(async () => {
  const N=v=>({kind:'Name',value:v});const F=(n,sub,args)=>({kind:'Field',name:N(n),...(args?{arguments:args}:{}),...(sub?{selectionSet:{kind:'SelectionSet',selections:sub}}:{})});
  const Var=n=>({kind:'Variable',name:N(n)});const NN=t=>({kind:'NonNullType',type:{kind:'NamedType',name:N(t)}});const T=t=>({kind:'NamedType',name:N(t)});
  const qDoc={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'query',name:N('getAllTypeColorsCombined'),variableDefinitions:[{kind:'VariableDefinition',variable:Var('search'),type:T('String')},{kind:'VariableDefinition',variable:Var('after'),type:T('Int')},{kind:'VariableDefinition',variable:Var('limit'),type:T('Int')}],
    selectionSet:{kind:'SelectionSet',selections:[F('getAllTypeColorsCombined',[F('colors',[F('id'),F('name'),F('colorType')])],['search','after','limit'].map(n=>({kind:'Argument',name:N(n),value:Var(n)})))]}}]};
  const mDoc={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'mutation',name:N('addLibraryColor'),variableDefinitions:[{kind:'VariableDefinition',variable:Var('input'),type:NN('AddColorInput')}],
    selectionSet:{kind:'SelectionSet',selections:[F('addLibraryColor',[F('id'),F('name')],[{kind:'Argument',name:N('addColorInput'),value:Var('input')}])]}}]};
  const out={};
  for (const name of %s) {
    const q=await window.__APOLLO_CLIENT__.query({query:qDoc,fetchPolicy:'no-cache',errorPolicy:'all',variables:{search:name,after:0,limit:50}});
    const list=(q.data&&q.data.getAllTypeColorsCombined&&q.data.getAllTypeColorsCombined.colors)||[];
    const hit=list.filter(c=>String(c.name||'').trim().toLowerCase()===name.trim().toLowerCase()&&String(c.colorType||'MyColor')==='MyColor');
    if (hit.length===1) { out[name]={id:hit[0].id,created:false}; continue; }
    if (hit.length>1) { out[name]={error:'mehrdeutig ('+hit.length+' Farben)'}; continue; }
    const r=await window.__APOLLO_CLIENT__.mutate({mutation:mDoc,errorPolicy:'all',variables:{input:{name}}});
    const id=r.data&&r.data.addLibraryColor&&r.data.addLibraryColor.id;
    out[name]=id?{id,created:true}:{error:(r.errors||[]).map(e=>e.message.slice(0,150)).join(';')||'keine Antwort'};
  }
  return out;
})()"""


def run_browser(js, label="browser"):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(BROWSER), timeout=600)
    if r.returncode:
        raise RuntimeError("%s gescheitert: %s" % (label, (r.stderr or r.stdout)[-300:]))
    return json.loads(r.stdout)


def ensure_colors(names):
    names = sorted({n for n in names if n})
    return run_browser(COLOR_JS % json.dumps(names), "Farben") if names else {}


LINK_JS = ("(async()=>{const N=v=>({kind:'Name',value:v});const F=(n,sub,args)=>({kind:'Field',name:N(n),...(args?{arguments:args}:{}),...(sub?{selectionSet:{kind:'SelectionSet',selections:sub}}:{})});"
           "const Var=n=>({kind:'Variable',name:N(n)});const NN=t=>({kind:'NonNullType',type:{kind:'NamedType',name:N(t)}});"
           "const doc={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'mutation',name:N('updateProductVariantFn'),variableDefinitions:[['productId','String'],['variantId','String'],['input','UpdateProductVariantInput']].map(([n,t])=>({kind:'VariableDefinition',variable:Var(n),type:NN(t)})),"
           "selectionSet:{kind:'SelectionSet',selections:[F('updateProductVariant',[F('id'),F('colorId')],['productId','variantId','input'].map(n=>({kind:'Argument',name:N(n),value:Var(n)})))]}}]};"
           "const res=[];for(const l of %s){const r=await window.__APOLLO_CLIENT__.mutate({mutation:doc,errorPolicy:'all',variables:{productId:l.productId,variantId:l.variantId,input:{name:l.name,colorId:l.colorId,colorType:'MyColor'}}});"
           "res.push({n:l.name,err:(r.errors||[]).map(e=>e.message.slice(0,200)),colorId:r.data&&r.data.updateProductVariant&&r.data.updateProductVariant.colorId});}return res;})()")


UVP_KEY, EK_KEY, KATCODE_KEY = "muxy5365hi2xhz_uvp", "muxy5sc1s5a8yw_einkaufspreis", "mv6jnln121cc81_kategorie_code"


def field_patch(spec, product):
    """REST-PUT-Koerper fuer Barcode/UVP/Einkaufspreis (customFields werden vom PUT KOMPLETT ersetzt -> vorhandene zusammenfuehren) oder None, wenn nichts zu schreiben ist."""
    cf = dict(product.get("customFields") or {})
    add = {k: v for k, v in ((UVP_KEY, spec.get("uvp")), (EK_KEY, spec.get("purchase_price"))) if isinstance(v, (int, float)) and not isinstance(v, bool)}
    if spec.get("category_code"):
        add[KATCODE_KEY] = spec["category_code"]
    body = {}
    if add:
        cf.update(add); body["customFields"] = cf
    if spec.get("barcode"):
        body["barcode"] = spec["barcode"]
    if not body:
        return None
    body["expectedUpdatedAt"] = product["updatedAt"]
    return body


def create_products(specs, find_product, log=print, put=None):
    """Fuehrt aus: Farben -> CSV -> Farb-Link. find_product(sku) liest per REST. Rueckgabe {sku: product} der angelegten Produkte. Bricht bei Unsicherheit ab."""
    if not specs:
        return {}
    for s in specs:
        if find_product(s["sku"]):
            raise RuntimeError("Produkt %s existiert schon: Abbruch (keine Dublette)" % s["sku"])
    colors = ensure_colors([c for s in specs for c in s["colors"]])
    bad = {k: v for k, v in colors.items() if v.get("error")}
    if bad:
        raise RuntimeError("Farben nicht eindeutig/anlegbar: %s" % bad)
    log("Farben: %s" % {k: ("neu" if v["created"] else "vorhanden") for k, v in colors.items()})
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "new_products.csv"; write_csv(specs, p)
        r = subprocess.run(["node", str(BROWSER / "import_csv.js"), str(p), "--commit"], capture_output=True, text=True, cwd=str(BROWSER), timeout=600)
        if "KLICK: IMPORT" not in r.stdout:
            raise RuntimeError("CSV-Import gescheitert: %s" % (r.stderr or r.stdout)[-300:])
    made = {}
    for s in specs:
        for _ in range(8):
            pr = find_product(s["sku"])
            if pr:
                break
            time.sleep(5)
        if not pr:
            raise RuntimeError("Produkt %s nach Import nicht gefunden" % s["sku"])
        made[s["sku"]] = pr
    links = [{"productId": made[s["sku"]]["id"], "variantId": v["id"], "name": v["name"], "colorId": colors[v["name"]]["id"]}
             for s in specs for v in made[s["sku"]].get("variants", []) if v.get("name") in colors]
    if links:
        res = run_browser(LINK_JS % json.dumps(links), "Farb-Link")
        bad = [x for x in res if x.get("err") or not x.get("colorId")]
        if bad:
            log("WARNUNG Farb-Link: %s" % bad)
    if put is None:
        import plm_client
        put = lambda pid, body: plm_client.call("PUT", "products/" + pid, body)[0]
    for sp in specs:
        pr = find_product(sp["sku"]) or made[sp["sku"]]
        body = field_patch(sp, pr)
        if body:
            log("Felder %s (Barcode/UVP/Einkaufspreis): HTTP %s" % (sp["sku"], put(pr["id"], body)))
    return made
