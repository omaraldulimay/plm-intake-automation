"""Volllauf fuer EINEN Fall (Lieferant -> Collection -> Farben -> Material -> Produkt mit Groessen -> Felder -> Stueckliste -> Maße -> Costing -> Sample -> Status -> PO).
Alles, was heute automatisch geht, in einer Reihenfolge. Schritte, die nur der MCP kann, schreibt das Skript als fertige bulk_actions-Listen (phase1/phase2),
der Rest (CSV-Import, Farb-Link, PO, Text-Felder, Pruefung) laeuft hier selbst.

  Fall-Datei: ein oder mehrere Produkte ("products": [...]; "product" = Kurzform fuer eins), PO-Positionen "po.items": [{"sku","price","lines":[{"color","sizes"}]}].
  python3 -m plm_intake.case_run phase1 <case.json>                 -> out/phase1_mcp.json  (Vendor, Collection, Farben, Material)
  python3 -m plm_intake.case_run run <case.json> --ids ids.json     -> CSV-Import, Farb-Link, Text-Felder, PO, out/phase2_mcp.json
  python3 -m plm_intake.case_run verify <case.json>                 -> liest alles zurueck und vergleicht
ids.json: {"material": "<libraryId>", "colors": {"ZZ4-Black": "<id>", ...}}  (aus den Ergebnissen von phase1)
"""
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import plm_client  # noqa: E402

BROWSER = ROOT / "plm_intake" / "browser"
UVP, EK, KATCODE, PLENTY, SPEC = ("muxy5365hi2xhz_uvp", "muxy5sc1s5a8yw_einkaufspreis", "mv6jnln121cc81_kategorie_code",
                                  "muxy47ha94z24q_plenty_produkt_id", "6acf777df6777ccef40a9499_spec_ma_e__gr__entabelle__produkt_mit_one_size_")


def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def outdir(case): d = ROOT / "output" / "intake" / "cases" / (case["key"] + "_out"); d.mkdir(parents=True, exist_ok=True); return d
def ms(d): y, m, dd = map(int, d.split("-")); return int(dt.datetime(y, m, dd, tzinfo=dt.timezone.utc).timestamp() * 1000)
def iso(d): return d + "T00:00:00.000Z"
def rest_list(path, **kw):
    s, d = plm_client.call("GET", path, **kw)
    return d.get("data", d) if isinstance(d, dict) else d


def phase1(case):
    acts = [{"tool": "create_record", "input": {"recordType": "manufacturer", "name": case["vendor"]["name"]}},
            {"tool": "create_record", "input": {"recordType": "collection", "name": case["collection"]}}]
    for c in case["colors"]:
        acts.append({"tool": "create_record", "input": {"recordType": "color", "name": c["name"], "hex": c["hex"], "data": {"code": c["code"]}}})
    m = case["material"]
    acts.append({"tool": "create_library_component", "input": {"name": m["name"], "type": m["type"], "categoryName": m["category"]}})
    for t in case.get("trims", []):
        acts.append({"tool": "create_library_component", "input": {"name": t["name"], "type": "TRIMS", "categoryName": t["category"]}})
    # Danach (phase1b, braucht die Material-ID): update_library_item mit colorways ZUERST, dann composition/structuredComposition/weight (sonst Fehler "reading 'color'")
    return acts


def normalize(case):
    """Kurzform (ein Produkt, po.lines) -> Mehrprodukt-Form. Defaults: jedes Produkt hat alle Farben, Material und Trims des Falls."""
    if "products" not in case: case["products"] = [case["product"]]
    po = case["po"]
    if "items" not in po:
        po["items"] = [{"sku": case["products"][0]["sku"], "price": po["price"], "lines": po["lines"]}]
    for p in case["products"]:
        p.setdefault("colors", [c["name"] for c in case["colors"]])
    skus = [p["sku"] for p in case["products"]]
    if len(set(skus)) != len(skus): raise SystemExit("SKU doppelt im Fall")
    for it in po["items"]:
        if it["sku"] not in skus: raise SystemExit("PO-Position mit unbekannter SKU " + it["sku"])
    return case


def products_csv(case, path):
    cols = ["Name", "Collection", "Category", "Status", "SKU", "Description", "Season", "Year", "Measurement Unit", "Sizes", "Variants", "Main Vendor", "Main Material", "Tags"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols)
        for p in case["products"]:   # Main Material NICHT per CSV: Menge/Yield lassen sich danach nicht per MCP aendern
            w.writerow([p["name"], case["collection"], case["category"], "", p["sku"], p.get("description", ""), "", p.get("year", ""), "cm", ", ".join(p["sizes"]),
                        ", ".join(p["colors"]), case["vendor"]["name"], "", p.get("tags", "")])


def find_product(sku):
    for x in rest_list("products", search=sku):
        if x.get("sku") == sku: return x
    return None


def browser(script_path):
    r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), str(script_path)], capture_output=True, text=True, cwd=BROWSER, timeout=300)
    if r.returncode: raise SystemExit("Browser-Skript Fehler: " + (r.stderr or r.stdout)[-500:])
    return json.loads(r.stdout)


LINK_JS = ("(async()=>{const N=v=>({kind:'Name',value:v});const F=(n,sub,args)=>({kind:'Field',name:N(n),...(args?{arguments:args}:{}),...(sub?{selectionSet:{kind:'SelectionSet',selections:sub}}:{})});"
           "const Var=n=>({kind:'Variable',name:N(n)});const NN=t=>({kind:'NonNullType',type:{kind:'NamedType',name:N(t)}});"
           "const doc={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'mutation',name:N('updateProductVariantFn'),variableDefinitions:[['productId','String'],['variantId','String'],['input','UpdateProductVariantInput']].map(([n,t])=>({kind:'VariableDefinition',variable:Var(n),type:NN(t)})),"
           "selectionSet:{kind:'SelectionSet',selections:[F('updateProductVariant',[F('id'),F('colorId')],['productId','variantId','input'].map(n=>({kind:'Argument',name:N(n),value:Var(n)})))]}}]};"
           "const res={links:[]};for(const l of %s){const r=await window.__APOLLO_CLIENT__.mutate({mutation:doc,errorPolicy:'all',variables:{productId:l.productId,variantId:l.variantId,input:{name:l.name,colorId:l.colorId,colorType:'MyColor'}}});"
           "res.links.push({n:l.name,err:(r.errors||[]).map(e=>e.message.slice(0,200)),colorId:r.data&&r.data.updateProductVariant&&r.data.updateProductVariant.colorId});}"
           "const c=await window.__createOrder(%s);res.po=c;return res;})()")


def run(case, ids):
    import time
    case = normalize(case); out = outdir(case); log = []; po = case["po"]
    for p in case["products"]:
        if find_product(p["sku"]): raise SystemExit("Produkt %s existiert schon: Abbruch (keine Dublette)" % p["sku"])
    products_csv(case, out / "import.csv")
    r = subprocess.run(["node", str(BROWSER / "import_csv.js"), str(out / "import.csv"), "--commit"], capture_output=True, text=True, cwd=BROWSER, timeout=300)
    log.append("CSV: " + ("ok" if "KLICK: IMPORT" in r.stdout else "FEHLER " + (r.stderr or r.stdout)[-300:]))
    prods = {}
    for p in case["products"]:
        for _ in range(8):
            prods[p["sku"]] = find_product(p["sku"])
            if prods[p["sku"]]: break
            time.sleep(5)
        if not prods[p["sku"]]: raise SystemExit("Produkt %s nach Import nicht gefunden" % p["sku"])
    vendor = [v for v in rest_list("vendors") if v.get("name") == case["vendor"]["name"]]
    if not vendor: raise SystemExit("Vendor nicht gefunden")
    color_ids = ids["colors"]; links = []; items = []; pieces = 0; total = 0.0
    for p in case["products"]:
        pr = prods[p["sku"]]; variants = {v["name"]: v["id"] for v in pr.get("variants", [])}
        for cname in p["colors"]:
            links.append({"productId": pr["id"], "variantId": variants[cname], "colorId": color_ids[cname], "name": cname})
    for it in po["items"]:
        pr = prods[it["sku"]]; p = next(x for x in case["products"] if x["sku"] == it["sku"]); variants = {v["name"]: v["id"] for v in pr.get("variants", [])}
        vl = []
        for ln in it["lines"]:
            price = ln.get("price", it["price"])
            amounts = [{"key": k, "quantity": q, "price": price, "cost": round(q * price, 2)} for k, q in ln["sizes"].items()]
            vl.append({"name": ln["color"], "variantId": variants.get(ln["color"]), "amounts": amounts})
            pieces += sum(a["quantity"] for a in amounts); total += sum(a["cost"] for a in amounts)
        items.append({"name": p["name"], "product": pr["id"], "variants": vl})
    total = round(total, 2)
    if abs(sum(x["amount"] for x in po["payments"]) - total) > 0.01: raise SystemExit("Zahlungen %.2f != Gesamtwert %.2f" % (sum(x["amount"] for x in po["payments"]), total))
    payload = {"title": po["title"], "manufacturer": vendor[0]["id"], "currency": po["currency"], "poNumber": po["poNumber"], "useCustomPoNumber": True,
               "exFactoryExpectedDate": iso(po["ex_factory"]), "etdEstimatedDate": iso(po["etd"]), "notes": po["notes"], "items": items,
               "payments": [{"name": x["name"], "status": x["status"], "amount": x["amount"], "dueDate": ms(x["due"]), "terms": x["terms"]} for x in po["payments"]],
               "totalCost": total, "totalNumberOfPieces": pieces, "assignees": []}
    (out / "browser_step.js").write_text(LINK_JS % (json.dumps(links), json.dumps(payload)), encoding="utf-8")
    res = browser(out / "browser_step.js"); log.append("Browser: " + json.dumps(res, ensure_ascii=False)[:500])
    bad = [l for l in res.get("links", []) if l.get("err") or not l.get("colorId")]
    if bad: log.append("WARNUNG Farb-Link: %s" % bad)
    # "Order ... not found" nach createOrder ist UNSICHER (Lesen direkt nach Schreiben kann scheitern, die PO ist oft trotzdem da): per REST pruefen, NIE blind wiederholen
    found = []
    for _ in range(6):
        found = [o for o in rest_list("orders", search=po["title"]) if o.get("title") == po["title"]]
        if found: break
        time.sleep(5)
    log.append("PO-Pruefung per REST: %d Treffer %s" % (len(found), [o["id"] for o in found]))
    if len(found) != 1: raise SystemExit("PO unsicher (%d Treffer): nichts wiederholen, Mensch prueft. Log: %s" % (len(found), log))
    # Text-Custom-Fields je Produkt per REST (ersetzt ALLE customFields -> vorher lesen und zusammenfuehren)
    acts = []
    for p in case["products"]:
        cur = find_product(p["sku"]); pid = cur["id"]; cf = dict(cur.get("customFields") or {})
        txt = {KATCODE: p.get("category_code"), PLENTY: p.get("plenty_id")}
        txt = {k: v for k, v in txt.items() if v}
        if txt:
            cf.update(txt)
            st, _ = plm_client.call("PUT", "products/" + pid, {"customFields": cf, "expectedUpdatedAt": cur["updatedAt"]})
            log.append("REST customFields %s: HTTP %s (500 moeglich, per Verify pruefen)" % (p["sku"], st))
        acts += phase2_for(case, p, pid, vendor[0]["id"], ids)
    if len(case["products"]) > 1:   # MCP verweigert mehrere Einzel-Runden mit demselben Lieferanten im selben Zug: eine Sammelrunde
        pids = [find_product(p["sku"])["id"] for p in case["products"]]
        acts.append({"tool": "create_bulk_sample_rounds", "input": {"manufacturerId": vendor[0]["id"], "manufacturerName": case["vendor"]["name"], "productIds": pids}})
    acts.append({"tool": "update_order_status", "input": {"entityId": found[0]["id"], "entityName": po["title"], "statusName": po.get("status", "Approved")}})
    (out / "phase2_mcp.json").write_text(json.dumps(acts, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "run_log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n".join(log)); print("Phase 2 (MCP): %d Aktionen in %s" % (len(acts), out / "phase2_mcp.json"))


def phase2_for(case, p, pid, vendor_id, ids):
    pn = p["name"]; acts = []
    upd = {"id": pid, "productName": pn}
    for k_in, k_out in (("barcode", "barcode"), ("estimated_cost", "estimatedCost"), ("season", "season"), ("year", "year"), ("tags", "tags")):
        if p.get(k_in) not in (None, ""): upd[k_out] = p[k_in]
    cf = {k: p[f] for k, f in ((UVP, "uvp"), (EK, "purchase_price"), (SPEC, "spec_text")) if p.get(f) not in (None, "")}
    if cf: upd["customFields"] = cf
    if len(upd) > 2: acts.append({"tool": "update_product", "input": upd})
    if p.get("measurements"):
        acts.append({"tool": "manage_base_measurements", "input": {"action": "bulk_add", "productId": pid, "productName": pn, "baseSize": "M" if "M" in p["sizes"] else p["sizes"][0],
                     "measurements": [{"name": m["name"], "code": m["code"], "requiredValue": m["value"], "tolPlus": m["tol"], "tolMinus": m["tol"], "unit": "cm"} for m in p["measurements"]]}})
    # Stueckliste per add_bom_component (Hauptmaterial mit Menge/Yield, Trims); Library-Items stehen in phase1
    if case.get("material"):
        acts.append({"tool": "add_bom_component", "input": {"productId": pid, "productName": pn, "libraryId": ids["material"], "libraryName": case["material"]["name"], "mainMaterial": True,
                     "quantity": p.get("bom_quantity", 1), "yield": p.get("bom_yield", 0), "yieldUnit": "meters"}})
    for t in case.get("trims", []):
        acts.append({"tool": "add_bom_component", "input": {"productId": pid, "productName": pn, "libraryId": ids["trims"][t["name"]], "libraryName": t["name"], "quantity": t.get("quantity", 1)}})
    if len(case["products"]) == 1:
        acts.append({"tool": "start_product_sampling_round", "input": {"productId": pid, "productName": pn, "manufacturerId": vendor_id, "manufacturerName": case["vendor"]["name"]}})
    if p.get("status"): acts.append({"tool": "update_product_status", "input": {"entityId": pid, "entityName": pn, "statusName": p["status"]}})
    if p.get("costing_rrp") is not None:
        acts.append({"tool": "create_costing_scenario", "input": {"productId": pid, "productName": pn, "name": p["name"] + " Costing v1", "importFromBom": True,
                     "rrp": p["costing_rrp"], "targetCost": p.get("costing_target", 0)}})
    return acts


def verify(case):
    case = normalize(case); probs = []
    for p in case["products"]:
        prod = find_product(p["sku"])
        if not prod: probs.append("Produkt fehlt: " + p["sku"]); continue
        if prod.get("sizes") != p["sizes"]: probs.append("%s Groessen %s != %s" % (p["sku"], prod.get("sizes"), p["sizes"]))
        for c in p["colors"]:
            v = next((v for v in prod.get("variants", []) if v["name"] == c), None)
            if not v: probs.append("%s Variante fehlt: %s" % (p["sku"], c))
            elif not v.get("color"): probs.append("%s Farbe nicht verknuepft: %s" % (p["sku"], c))
        if (prod.get("mainManufacturer") or {}).get("name") != case["vendor"]["name"]: probs.append("%s Hauptlieferant" % p["sku"])
    orders = [o for o in rest_list("orders", search=case["po"]["title"]) if o.get("title") == case["po"]["title"]]
    if len(orders) != 1: probs.append("PO-Anzahl %d" % len(orders))
    print("PROBLEME:" if probs else "ALLES OK (REST-Teil)", "; ".join(probs)); return probs


if __name__ == "__main__":
    cmd, case_p = sys.argv[1], sys.argv[2]; case = load(case_p)
    if cmd == "phase1":
        a = phase1(case); (outdir(case) / "phase1_mcp.json").write_text(json.dumps(a, indent=1, ensure_ascii=False)); print(json.dumps(a, ensure_ascii=False))
    elif cmd == "run": run(case, load(sys.argv[sys.argv.index("--ids") + 1]))
    elif cmd == "verify": verify(case)
