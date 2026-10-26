"""Projektkosten der Lieferanten-Projekte aus belegten Order-Positionen (Dry-Run, schreibt NICHTS).

Je Projekt-Produkt, das in Orders des Lieferanten vorkommt: Menge je Variante = Summe ueber alle Orders, Einkaufspreis = price der Order-Position.
Verschiedene Preise je Variante (mehrere Orders oder Groessen): nicht schreiben, melden. Variante nicht in selectedVariants des Projekt-Produkts: melden.
Ziel-Mutationen (App-GraphQL, Namen aus output/plm_datenmodell/graphql_operationen.json; Projekt-Costing-Zeile = variants[] von getProjectCosting):
  updateVariantQuantity(projectId, variantId, quantity)  |  updateVariantBuyingPriceSimple(projectId, variantId, buyingPrice, projectProductId)
  updateVariantVendor(projectId, variantId, vendorId)   |  bulkUpdateVariantBuyingPrices(projectId, updates)
--apply (Pilot, nur PILOT_VENDORS): je Variante mit belegter Menge+Preis (kein Konflikt, Preis > 0) updateVariantQuantity und
updateVariantBuyingPriceSimple; vorhandene Werte > 0 werden nie ueberschrieben; Backup (getProjectCosting) nach output/backup/, Zuruecklesen je Projekt
mit Summenpruefung (Menge*Preis = erwartete Summe), Abbruch bei Abweichung. --test-one schreibt nur die erste Variante des ersten Projekts.
Aufruf:  .venv/bin/python -m plm_intake.project_costing [--out ...] [--vendor TEIL ...] [--apply [--test-one]]"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from plm_intake import vendor_projects as vp

ROOT = Path(__file__).resolve().parents[1]
PILOT_VENDORS = ["LIEFERANT_X", "LIEFERANT_AH", "Lieferant U"]
SEL = "id projectId variants { id projectProductId variantId variantName quantity buyingPrice targetCost estimatedCost estimatedRrp sizeQuantities { sizeId sizeTitle quantity } }"
_HEAD = r'''
const N=v=>({kind:'Name',value:v}); const V=n=>({kind:'Variable',name:N(n)}); const c=window.__APOLLO_CLIENT__;
const parseSel=s=>{const t=s.match(/[{}]|\w+/g);let i=0;const rec=()=>{const out=[];while(i<t.length&&t[i]!=='}'){const n=t[i++];const f={kind:'Field',name:N(n),arguments:[]};if(t[i]==='{'){i++;f.selectionSet={kind:'SelectionSet',selections:rec()};i++;}out.push(f);}return out;};return rec();};
const clean=a=>a===undefined||a===null?a:JSON.parse(JSON.stringify(a,(k,v)=>(k==='__typename'?undefined:v)));
const NN=(t)=>({kind:'NonNullType',type:{kind:'NamedType',name:N(t)}});
const mk=(op,name,vars,field,args,sel)=>({kind:'Document',definitions:[{kind:'OperationDefinition',operation:op,name:N(name),variableDefinitions:vars.map(([n,t,nn])=>({kind:'VariableDefinition',variable:V(n),type:nn?NN(t):{kind:'NamedType',name:N(t)}})),selectionSet:{kind:'SelectionSet',selections:[{kind:'Field',name:N(field),arguments:args.map(([a,v])=>({kind:'Argument',name:N(a),value:V(v)})),selectionSet:{kind:'SelectionSet',selections:parseSel(sel)}}]}}]});
const SEL=__SEL__;
const GET=mk('query','G',[['projectId','ID',1]],'getProjectCosting',[['projectId','projectId']],SEL);
const UQ=mk('mutation','UQ',[['projectId','ID',1],['variantId','String',1],['quantity','Int',1]],'updateVariantQuantity',[['projectId','projectId'],['variantId','variantId'],['quantity','quantity']],SEL);
const UP=mk('mutation','UP',[['projectId','ID',1],['variantId','String',1],['buyingPrice','Float',1],['projectProductId','ID']],'updateVariantBuyingPriceSimple',[['projectId','projectId'],['variantId','variantId'],['buyingPrice','buyingPrice'],['projectProductId','projectProductId']],SEL);
const get=async id=>{const r=await c.query({query:GET,variables:{projectId:id},fetchPolicy:'no-cache',errorPolicy:'all'});return {data:clean(r.data&&r.data.getProjectCosting),err:(r.errors||[]).map(e=>e.message.slice(0,200))};};
const mut=async(m,v)=>{try{const r=await c.mutate({mutation:m,variables:v,errorPolicy:'all'});return {err:(r.errors||[]).map(e=>e.message.slice(0,300))};}catch(e){const ne=e.networkError&&e.networkError.result&&e.networkError.result.errors;return {err:(ne||[{message:String(e.message)}]).map(x=>String(x.message).slice(0,300))};}};
'''
JS_GET = "(async()=>{" + _HEAD + "return await get(__PID__);})()"
# jobs: [{variantId, projectProductId, qty (oder null), price (oder null)}]
JS_SET = ("(async()=>{" + _HEAD + "const out=[];for(const j of __JOBS__){const o={variantId:j.variantId};"
          "if(j.qty!=null){o.q=await mut(UQ,{projectId:__PID__,variantId:j.variantId,quantity:j.qty});}"
          "if(j.price!=null&&!(o.q&&o.q.err.length)){o.p=await mut(UP,{projectId:__PID__,variantId:j.variantId,buyingPrice:j.price,projectProductId:j.projectProductId});}"
          "out.push(o);}return out;})()")
MUTATIONS = ["updateVariantQuantity", "updateVariantBuyingPriceSimple", "updateVariantVendor", "bulkUpdateVariantBuyingPrices"]


def plan(vendors, orders, projects):
    """-> {projekte: [ {project_id, vendor, vendor_id, zeilen[], konflikte[], fremd[], summe, order_summe, order_summe_pos, orders} ]}"""
    vname = {v["id"]: v.get("name") or "" for v in vendors}
    by_name = {}
    for p in projects:
        by_name.setdefault(vp.norm(p.get("name")), []).append(p)
    out = []
    for vid in sorted(vname, key=lambda v: vname[v].casefold()):
        hit = by_name.get(vp.norm(vname[vid]), [])
        if len(hit) != 1 or not vp.norm(vname[vid]):
            continue
        proj = hit[0]
        sel = {str(x["productId"]): set(x.get("selectedVariants") or []) for x in proj.get("products") or []}
        agg, fremd = {}, []
        nord, order_sum, pos_sum = 0, 0.0, 0.0
        for o in orders:
            if vp.is_test(o.get("title")) or vp.order_vendor_id(o) != vid:
                continue
            nord += 1
            order_sum += float(o.get("totalCost") or 0)
            for it in o.get("items") or []:
                pid = str((it.get("product") or {}).get("id") or "")
                for v in it.get("variants") or []:
                    for a in v.get("amounts") or []:
                        pos_sum += float(a.get("quantity") or 0) * float(a.get("price") or 0)
                    if pid not in sel:
                        fremd.append("%s | %s (Produkt nicht im Projekt)" % (o.get("title"), it.get("name")))
                        break
                    vv = v.get("variantId")
                    if vv not in sel[pid]:
                        fremd.append("%s | %s / %s (Variante nicht im Projekt)" % (o.get("title"), it.get("name"), v.get("name")))
                        continue
                    g = agg.setdefault((pid, vv), {"produkt": it.get("name"), "variante": v.get("name"), "qty": 0, "preise": {}, "orders": set()})
                    for a in v.get("amounts") or []:
                        q = float(a.get("quantity") or 0)
                        if q <= 0:
                            continue
                        g["qty"] += q
                        g["preise"][round(float(a.get("price") or 0), 4)] = o.get("title")
                        g["orders"].add(o.get("title"))
        zeilen, konf, summe = [], [], 0.0
        for (pid, vv), g in sorted(agg.items(), key=lambda kv: (kv[1]["produkt"] or "", kv[1]["variante"] or "")):
            row = {"productId": pid, "variantId": vv, "produkt": g["produkt"], "variante": g["variante"], "menge": int(g["qty"]),
                   "preise": sorted(g["preise"]), "orders": sorted(g["orders"])}
            if len(row["preise"]) > 1 or not row["preise"] or row["preise"][0] <= 0:
                konf.append(row)
            else:
                row["preis"] = row["preise"][0]
                summe += row["menge"] * row["preis"]
                zeilen.append(row)
        if nord or zeilen:
            out.append({"project_id": proj["id"], "vendor": vname[vid], "vendor_id": vid, "zeilen": zeilen, "konflikte": konf, "fremd": sorted(set(fremd)),
                        "summe": round(summe, 2), "order_summe": round(order_sum, 2), "order_summe_pos": round(pos_sum, 2), "orders": nord})
    return {"projekte": out}


def _fill(js, **kw):
    for k, v in kw.items():
        js = js.replace("__%s__" % k, json.dumps(v))
    return js


def run_js(js):
    from plm_intake.po_ids import run_js as _run
    return _run(js)


def costing_sum(costing):
    return round(sum(float(v.get("quantity") or 0) * float(v.get("buyingPrice") or 0) for v in (costing or {}).get("variants") or []), 2)


def build_jobs(proj, costing):
    """-> (jobs, uebersprungen). Nur belegte Menge+Preis; vorhandene Werte > 0 bleiben (abweichende werden gemeldet)."""
    cv = {v["variantId"]: v for v in (costing or {}).get("variants") or []}
    jobs, skip = [], []
    for r in proj["zeilen"]:
        v = cv.get(r["variantId"])
        if not v:
            skip.append("%s / %s: nicht in Projekt-Costing" % (r["produkt"], r["variante"]))
            continue
        if r["preis"] <= 0 or r["menge"] <= 0:
            continue
        j = {"variantId": r["variantId"], "projectProductId": v.get("projectProductId"), "qty": None, "price": None, "name": "%s / %s" % (r["produkt"], r["variante"])}
        for key, cur, soll, nm in (("qty", v.get("quantity"), r["menge"], "Menge"), ("price", v.get("buyingPrice"), r["preis"], "Preis")):
            if cur and float(cur) > 0:
                if abs(float(cur) - soll) > 1e-9:
                    skip.append("%s: %s vorhanden %s != %s (nicht ueberschrieben)" % (j["name"], nm, cur, soll))
            else:
                j[key] = soll
        if j["qty"] is not None or j["price"] is not None:
            jobs.append(j)
    return jobs, skip


def apply_pilot(pl, only, test_one=False, runner=run_js, log=print):
    """Schreibt die Pilot-Projekte. Backup vorher, Zuruecklesen und Summenpruefung nachher; bricht bei Abweichung ab."""
    res = []
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    for p in pl["projekte"]:
        if not any(o.casefold() in p["vendor"].casefold() for o in only) or not any(o.casefold() in p["vendor"].casefold() for o in PILOT_VENDORS):
            continue
        if p["konflikte"]:
            log("%s: Konflikte, uebersprungen" % p["vendor"]); continue
        before = runner(_fill(JS_GET, SEL=SEL, PID=p["project_id"]))
        if before.get("err") or not before.get("data"):
            raise RuntimeError("%s: getProjectCosting: %s" % (p["vendor"], before.get("err")))
        bk = ROOT / "output" / "backup" / ("projektkosten_vor_%s_%s.json" % (p["vendor"].split()[0].lower().strip("(),"), stamp))
        bk.parent.mkdir(parents=True, exist_ok=True)
        bk.write_text(json.dumps(before["data"], ensure_ascii=False, indent=1), encoding="utf-8")
        jobs, skip = build_jobs(p, before["data"])
        if test_one:
            jobs = jobs[:1]
        log("%s: %d Varianten zu schreiben, %d Hinweise, Backup %s" % (p["vendor"], len(jobs), len(skip), bk))
        out = runner(_fill(JS_SET, SEL=SEL, PID=p["project_id"], JOBS=jobs)) if jobs else []
        errs = [o for o in out if (o.get("q") or {}).get("err") or (o.get("p") or {}).get("err")]
        after = runner(_fill(JS_GET, SEL=SEL, PID=p["project_id"]))["data"]
        s_after = costing_sum(after)
        r = {"vendor": p["vendor"], "project_id": p["project_id"], "geschrieben": len(jobs), "fehler": errs, "hinweise": skip, "summe_vorher": costing_sum(before["data"]),
             "summe_nachher": s_after, "erwartet": p["summe"], "ok": not errs and (test_one or abs(s_after - p["summe"]) < 0.01)}
        res.append(r)
        log(json.dumps(r, ensure_ascii=False))
        if not r["ok"]:
            log("ABBRUCH: Abweichung bei %s" % p["vendor"]); break
        if test_one:
            break
    return res


def report(pl):
    P = pl["projekte"]
    L = ["# Projektkosten Dry-Run (nichts geschrieben)", "",
         "Quelle: Order-Positionen je Lieferant (Menge = Summe ueber Orders, Preis = price je Variante). Schreibweg: %s." % ", ".join(MUTATIONS), "",
         "| Projekt | Orders | Zeilen | Konflikte | nicht im Projekt | Summe Projekt (belegt) | Summe Order-Positionen | totalCost Orders | Differenz Projekt-totalCost |",
         "|---|---|---|---|---|---|---|---|---|"]
    for p in sorted(P, key=lambda p: -p["summe"]):
        L.append("| %s | %d | %d | %d | %d | %.2f | %.2f | %.2f | %.2f |" % (p["vendor"], p["orders"], len(p["zeilen"]), len(p["konflikte"]), len(p["fremd"]),
                                                                           p["summe"], p["order_summe_pos"], p["order_summe"], p["summe"] - p["order_summe"]))
    L += ["", "Summe: Projekt %.2f | Order-Positionen %.2f | totalCost %.2f" % (sum(p["summe"] for p in P), sum(p["order_summe_pos"] for p in P), sum(p["order_summe"] for p in P)), ""]
    L.append("## Konflikte (verschiedene Preise oder Preis 0 je Variante: nicht schreiben)")
    for p in P:
        for r in p["konflikte"]:
            L.append("- %s | %s / %s | Menge %d | Preise %s | Orders %s" % (p["vendor"], r["produkt"], r["variante"], r["menge"], r["preise"], "; ".join(r["orders"])))
    L += ["", "## Order-Positionen ausserhalb der Projekt-Produkte/-Varianten"]
    for p in P:
        for f in p["fremd"]:
            L.append("- %s | %s" % (p["vendor"], f))
    L += ["", "## Schreibzeilen je Projekt (Variante: Menge x Preis)"]
    for p in P:
        if p["zeilen"]:
            L += ["", "### %s (%d Zeilen, %.2f)" % (p["vendor"], len(p["zeilen"]), p["summe"])]
            L += ["- %s / %s: %d x %.4f" % (r["produkt"], r["variante"], r["menge"], r["preis"]) for r in p["zeilen"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "output" / "phase2" / "B27" / "projektkosten_dryrun.md"))
    ap.add_argument("--vendor", "--projekt", dest="vendor", action="append", help="Teil des Lieferanten-/Projektnamens (mehrfach); begrenzt Ausgabe und --apply")
    ap.add_argument("--apply", action="store_true", help="Pilot-Schreiben (nur PILOT_VENDORS)")
    ap.add_argument("--test-one", action="store_true", help="mit --apply: nur eine Variante des ersten Projekts")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    import plm_client
    from plm_intake.context import fetch_all
    pl = plan(fetch_all(plm_client.call, "vendors"), fetch_all(plm_client.call, "orders"), fetch_all(plm_client.call, "projects"))
    if a.vendor:
        pl["projekte"] = [p for p in pl["projekte"] if any(o.casefold() in p["vendor"].casefold() for o in a.vendor)]
    if a.apply:
        projects = {p["id"]: p for p in fetch_all(plm_client.call, "projects")}
        for p in pl["projekte"]:
            print("projectedCost vorher %s: %s" % (p["vendor"], projects.get(p["project_id"], {}).get("projectedCost")))
        res = apply_pilot(pl, a.vendor or PILOT_VENDORS, a.test_one)
        projects = {p["id"]: p for p in fetch_all(plm_client.call, "projects")}
        for r in res:
            print("projectedCost nachher %s: %s" % (r["vendor"], projects.get(r["project_id"], {}).get("projectedCost")))
        return 0 if res and all(r["ok"] for r in res) else 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(report(pl), encoding="utf-8")
    print("geschrieben:", a.out)
    for p in sorted(pl["projekte"], key=lambda p: -p["summe"])[:10]:
        print("%-34s zeilen %3d konfl %2d summe %.2f order_pos %.2f totalCost %.2f" % (p["vendor"][:34], len(p["zeilen"]), len(p["konflikte"]), p["summe"], p["order_summe_pos"], p["order_summe"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
