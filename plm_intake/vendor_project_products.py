"""Produkte in die Lieferanten-Projekte: je Projekt alle Produkte mit Main Vendor = Projektlieferant (mit ALLEN Varianten-IDs des Produkts).

Regeln: nur Hauptlieferant zaehlt (Produkte in Orders eines anderen Lieferanten = Klaerfall, nie automatisch); Test-Produkte (ZZ-/T1-/TEST in Name/SKU)
und Test-Lieferanten (ZZ...) nie; Produkte ohne Variante werden uebersprungen (Warnung). Vorher wird gelesen, was im Projekt schon ist: ein Produkt
wird nie doppelt aufgenommen, nie etwas entfernt. Projekt per normalisiertem Namen = Lieferantenname; mehrdeutig -> uebersprungen.
Schreiben per App-GraphQL im Browser: addMultipleProductsToProject(projectId, addMultipleProductsInput{products:[{productId,productName,selectedVariants,sourceData:null}]})
in Bloecken zu BLOCK=50; max. MAX_PRODUCTS pro Lauf (auto_run: 100). Vorzustand: output/backup/vendor_project_products_vor_<Zeit>.json.
Zuruecklesen: je Projekt productCount = erwartete Zahl und jedes Produkt genau einmal.
Dry-Run ist Standard:  python3 -m plm_intake.vendor_project_products [--apply] [--vendor NAME] [--limit N]"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from plm_intake import vendor_projects as vp

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "output" / "backup"
BLOCK = 50
MAX_PRODUCTS = 100
MIN_PRODUCTS_FOR_PROJECT = 5


def product_vendor_id(p):
    m = p.get("mainManufacturer")
    return (m.get("id") or m.get("_id")) if isinstance(m, dict) else (m or None)


def is_test_product(p):
    return vp.is_test(p.get("name")) or vp.is_test(p.get("sku"))


def test_vendor(name):
    return bool(re.match(r"(?i)\s*zz", name or ""))


def vendor_products(vendors, products):
    """-> {vendor_id: [produkt,...]} (nur echte Produkte mit Main Vendor, kein Test-Lieferant), sortiert nach Name."""
    vname = {v["id"]: v.get("name") or "" for v in vendors}
    out = {}
    for p in products:
        vid = product_vendor_id(p)
        if not vid or vid not in vname or not vp.norm(vname[vid]) or test_vendor(vname[vid]) or is_test_product(p):
            continue
        out.setdefault(vid, []).append(p)
    for l in out.values():
        l.sort(key=lambda p: (p.get("name") or "", p["id"]))
    return out


def vendors_needing_project(vendors, products, minimum=MIN_PRODUCTS_FOR_PROJECT):
    """Lieferanten-IDs mit mindestens `minimum` echten Produkten (Main Vendor)."""
    return {vid for vid, l in vendor_products(vendors, products).items() if len(l) >= minimum}


def plan(vendors, products, projects, limit=MAX_PRODUCTS, only_vendor=None):
    """-> dict rows (je Lieferant), adds (Bloecke je Projekt, begrenzt), warnings. projects: [{id,name,products:[{productId}]}].
    Fehlt das Projekt noch (wird von vendor_projects angelegt), steht project_id None und der Lieferant erscheint nur in rows (nicht in adds)."""
    vname = {v["id"]: v.get("name") or "" for v in vendors}
    by_name = {}
    for p in projects:
        by_name.setdefault(vp.norm(p.get("name")), []).append(p)
    vprod = vendor_products(vendors, products)
    rows, adds, warnings = [], [], []
    left = limit
    for vid in sorted(vprod, key=lambda v: vname[v].casefold()):
        if only_vendor and vp.norm(only_vendor) != vp.norm(vname[vid]):
            continue
        hit = by_name.get(vp.norm(vname[vid]), [])
        want = vprod[vid]
        novar = [p for p in want if not [v for v in p.get("variants") or [] if v.get("id")]]
        want = [p for p in want if p not in novar]
        row = {"vendor": vname[vid], "produkte": len(want), "varianten": sum(len(p["variants"]) for p in want), "project_id": None,
               "im_projekt": 0, "fehlt": len(want), "ohne_variante": len(novar)}
        if novar:
            warnings.append("%s: %d Produkt(e) ohne Variante nicht aufgenommen" % (vname[vid], len(novar)))
        if len(hit) > 1:
            warnings.append("Mehrere Projekte mit Namen '%s', Produkte uebersprungen" % vname[vid])
            row["status"] = "mehrdeutig"; rows.append(row); continue
        if not hit:
            row["status"] = "Projekt fehlt (wird angelegt)" if len(want) >= MIN_PRODUCTS_FOR_PROJECT else "kein Projekt (erst bei erster Order)"
            rows.append(row); continue
        proj = hit[0]
        have = {str(x.get("productId")) for x in proj.get("products") or []}
        todo = [p for p in want if p["id"] not in have]
        row.update(project_id=proj["id"], im_projekt=len(have), fehlt=len(todo), status="ok" if not todo else "offen")
        rows.append(row)
        take = todo[:max(0, left)]
        left -= len(take)
        if len(todo) > len(take):
            row["status"] = "offen (Limit)"
        if take:
            adds.append({"project_id": proj["id"], "vendor": vname[vid], "have": len(have),
                         "products": [{"productId": p["id"], "productName": p.get("name") or "", "selectedVariants": [v["id"] for v in p["variants"] if v.get("id")], "sourceData": None} for p in take]})
    return {"rows": rows, "adds": adds, "warnings": warnings}


# ---------------- Browser (GraphQL) ----------------
PSEL = "id name productCount stylesCount activeSamples products { _id productId productName selectedVariants sourceData addedAt }"

_READ = vp._HEAD + r'''
const readP=async()=>{const d={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'query',selectionSet:{kind:'SelectionSet',selections:[{kind:'Field',name:N('projects'),
  arguments:[{kind:'Argument',name:N('limit'),value:{kind:'IntValue',value:'1000'}}],selectionSet:{kind:'SelectionSet',selections:parseSel(__PSEL__)}}]}}]};
  const r=await c.query({query:d,fetchPolicy:'no-cache',errorPolicy:'all'});
  return {data:r.data&&r.data.projects,err:(r.errors||[]).map(e=>e.message.slice(0,200))};};
'''

JS_READ = "(async()=>{" + _READ.replace("__PSEL__", json.dumps(PSEL)) + "const r=await readP(); return {projects:r.data?clean(r.data):null,err:r.err};})()"

JS_WRITE = "(async()=>{" + _READ.replace("__PSEL__", json.dumps(PSEL)) + r'''
const addDoc=doc('mutation',[['projectId','ID'],['addMultipleProductsInput','AddMultipleProductsToProjectInput']],'addMultipleProductsToProject',
  [{kind:'Argument',name:N('projectId'),value:V('projectId')},{kind:'Argument',name:N('addMultipleProductsInput'),value:V('addMultipleProductsInput')}],__PSEL__);
const out={blocks:[],stop:null};
for(const b of __BLOCKS__){
  try{
    const r=await c.mutate({mutation:addDoc,variables:{projectId:b.project_id,addMultipleProductsInput:{products:b.products}},errorPolicy:'all'});
    const err=(r.errors||[]).map(e=>e.message.slice(0,200));
    const p=r.data&&r.data.addMultipleProductsToProject;
    out.blocks.push({project:b.project_id,n:b.products.length,err:err.length?err:null,productCount:p?p.productCount:null});
    if(err.length){out.stop='Block fehlgeschlagen: '+b.project_id;break;}
  }catch(e){out.blocks.push({project:b.project_id,n:b.products.length,err:String(e.message).slice(0,200)});out.stop='Block unsicher: '+b.project_id;break;}
}
const after=await readP();
out.after=after.data?clean(after.data):null; out.afterErr=after.err;
return out;})()'''.replace("__PSEL__", json.dumps(PSEL))


def read_projects(runner=vp.run_js):
    res = runner(JS_READ)
    if res.get("projects") is None:
        raise RuntimeError("Projekte nicht lesbar: %s" % res.get("err"))
    return res["projects"]


def blocks_of(pl, size=BLOCK):
    out = []
    for a in pl["adds"]:
        for i in range(0, len(a["products"]), size):
            out.append({"project_id": a["project_id"], "products": a["products"][i:i + size]})
    return out


def write(pl, runner=vp.run_js):
    return runner(JS_WRITE.replace("__BLOCKS__", json.dumps(blocks_of(pl))))


def verify(pl, res):
    """-> (neu_ok, fehler[]). Je Projekt: productCount == vorher + neu, len(products)==productCount, jedes geplante Produkt genau 1x, keine Doppelten."""
    after = res.get("after")
    if after is None:
        return 0, ["Zuruecklesen fehlgeschlagen: %s" % res.get("afterErr")]
    byid = {p["id"]: p for p in after}
    errs = [("Block %s: %s" % (b.get("project"), b["err"])) for b in res.get("blocks") or [] if b.get("err")]
    if res.get("stop"):
        errs.append("Lauf gestoppt: %s" % res["stop"])
    ok = 0
    for a in pl["adds"]:
        p = byid.get(a["project_id"])
        if not p:
            errs.append("%s: Projekt beim Zuruecklesen nicht gefunden" % a["vendor"]); continue
        ids = [str(x.get("productId")) for x in p.get("products") or []]
        want = a["have"] + len(a["products"])
        dup = len(ids) - len(set(ids))
        miss = [x["productId"] for x in a["products"] if ids.count(x["productId"]) != 1]
        if p.get("productCount") != want or len(ids) != want or dup or miss:
            errs.append("%s: Zuruecklesen unstimmig (productCount %s, Eintraege %d, erwartet %d, doppelt %d, fehlend/mehrfach %d)" % (
                a["vendor"], p.get("productCount"), len(ids), want, dup, len(miss)))
        else:
            ok += len(a["products"])
    return ok, errs


def backup(projects, pl, now=None):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    p = BACKUP_DIR / ("vendor_project_products_vor_%s.json" % (now or dt.datetime.now()).strftime("%Y-%m-%d_%H%M%S"))
    p.write_text(json.dumps({"projects": projects, "plan": pl}, ensure_ascii=False, indent=1))
    return p


def run(vendors, products, apply=False, limit=MAX_PRODUCTS, only_vendor=None, runner=vp.run_js, backup_fn=backup):
    """-> (zeilen, ergebnis{neu,fehler,warnungen,plan}). Trockenlauf liest nur."""
    projects = read_projects(runner)
    pl = plan(vendors, products, projects, limit, only_vendor)
    n = sum(len(a["products"]) for a in pl["adds"])
    res = {"neu": 0, "fehler": 0, "warnungen": list(pl["warnings"]), "plan": pl}
    L = ["- Projekt-Produkte: %d Produkte in %d Projekten zu verknuepfen (Limit %d)" % (n, len(pl["adds"]), limit)]
    L += ["- WARNUNG %s" % w for w in pl["warnings"]]
    if not apply:
        return ["- (Trockenlauf) nichts geschrieben"] + L, res
    if not n:
        return L + ["- nichts zu tun"], res
    L.append("- Backup: %s" % backup_fn(projects, pl))
    out = write(pl, runner)
    ok, errs = verify(pl, out)
    res.update(neu=ok, fehler=len(errs))
    L.append("- Projekt-Produkte: neu %d, Fehler %d" % (ok, len(errs)))
    L += ["- FEHLER %s" % e for e in errs[:8]]
    res["warnungen"] += ["Projekt-Produkte: %s" % e for e in errs[:5]]
    res["after"] = out.get("after")
    return L, res


# ---------------- Snapshot-Abgleich (checkProjectProductsSync / resyncProjectProducts) ----------------
# Projekt-Produkte tragen einen Snapshot (sourceData: Name, SKU, Varianten, updatedAt). checkProjectProductsSync(projectId) nennt, was im Katalog
# inzwischen anders ist; resyncProjectProducts(projectId, linkedProductIds = _id der Projekt-Produkte) zieht nach. Nur mit --resync, nie in auto_run.
SYNC_SEL = "outOfSyncCount outOfSyncProducts { linkedProductId productId productName changes { name { stored current } sku { stored current } variants { stored { count variants } current { count variants details } } updatedAt { stored current } } }"
_ARG_PID = "[{kind:'Argument',name:N('projectId'),value:V('projectId')}]"

JS_SYNC_CHECK = "(async()=>{" + vp._HEAD + """
const qd=doc('query',[['projectId','ID']],'checkProjectProductsSync',%s,%s);
const out=[];
for(const pid of __PIDS__){
  const r=await c.query({query:qd,variables:{projectId:pid},fetchPolicy:'no-cache',errorPolicy:'all'});
  out.push({project:pid,data:r.data?clean(r.data.checkProjectProductsSync):null,err:(r.errors||[]).map(e=>e.message.slice(0,200))});
}
return {checks:out};})()""" % (_ARG_PID, json.dumps(SYNC_SEL))

JS_RESYNC = "(async()=>{" + vp._HEAD + """
const md=doc('mutation',[['projectId','ID'],['linkedProductIds','ID']],'resyncProjectProducts',
  [{kind:'Argument',name:N('projectId'),value:V('projectId')},{kind:'Argument',name:N('linkedProductIds'),value:V('linkedProductIds')}],'id productCount products { _id productId productName selectedVariants }');
md.definitions[0].variableDefinitions[1].type={kind:'NonNullType',type:{kind:'ListType',type:{kind:'NonNullType',type:{kind:'NamedType',name:N('ID')}}}};
const out=[];
for(const j of __JOBS__){
  try{const r=await c.mutate({mutation:md,variables:{projectId:j.project_id,linkedProductIds:j.linked},errorPolicy:'all'});
    const p=r.data&&r.data.resyncProjectProducts;
    out.push({project:j.project_id,err:(r.errors||[]).map(e=>e.message.slice(0,200)),productCount:p?p.productCount:null,n:p?(p.products||[]).length:null});
  }catch(e){out.push({project:j.project_id,err:[String(e.message).slice(0,200)]});break;}
}
return {resync:out};})()"""


def check_sync(projects, runner=vp.run_js):
    """Read-only: Projekte mit Produkten -> {project_id: {outOfSyncCount, outOfSyncProducts[...]}}."""
    pids = [p["id"] for p in projects if p.get("productCount")]
    if not pids:
        return {}
    res = runner(JS_SYNC_CHECK.replace("__PIDS__", json.dumps(pids)))
    return {c["project"]: c["data"] if c.get("data") is not None else {"err": c.get("err")} for c in res.get("checks") or []}


def real_change(x):
    """Frisch aufgenommene Produkte melden sofort 'Variant ... description changed' (null vs. leer) = Rauschen. Echt: Name/SKU/updatedAt geaendert,
    Variantenzahl anders oder andere Detailmeldung als nur 'description changed'."""
    ch = x.get("changes") or {}
    if ch.get("name") or ch.get("sku") or ch.get("updatedAt"):
        return True
    v = ch.get("variants")
    if v:
        if (v.get("stored") or {}).get("count") != (v.get("current") or {}).get("count"):
            return True
        return any(not str(d).endswith("description changed") for d in (v.get("current") or {}).get("details") or [])
    return False


def resync(checks, runner=vp.run_js):
    """Zieht ausser-Takt-Produkte nach (nur Snapshot der Projekt-Produkte). Danach erneut pruefen -> outOfSyncCount muss 0 sein."""
    jobs = [{"project_id": pid, "linked": [x["linkedProductId"] for x in c.get("outOfSyncProducts") or [] if real_change(x)]} for pid, c in checks.items() if c.get("outOfSyncCount")]
    jobs = [j for j in jobs if j["linked"]]
    return runner(JS_RESYNC.replace("__JOBS__", json.dumps(jobs))) if jobs else {"resync": []}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--vendor", help="nur dieser Lieferant (Pilot)")
    ap.add_argument("--sync", action="store_true", help="nur lesen: Projekt-Produkte ausser Takt mit dem Katalog zeigen")
    ap.add_argument("--resync", action="store_true", help="ausser-Takt-Produkte nachziehen (resyncProjectProducts)")
    ap.add_argument("--limit", type=int, default=MAX_PRODUCTS)
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    import plm_client
    from plm_intake.context import fetch_all
    if a.sync or a.resync:
        ch = check_sync(read_projects())
        for pid, c in ch.items():
            print(pid, c.get("outOfSyncCount"), json.dumps(c.get("outOfSyncProducts") or c.get("err"), ensure_ascii=False)[:600])
        if a.resync:
            print(json.dumps(resync(ch), ensure_ascii=False)[:800])
            print("danach:", {k: v.get("outOfSyncCount") for k, v in check_sync(read_projects()).items()})
        return 0
    vendors, products = fetch_all(plm_client.call, "vendors"), fetch_all(plm_client.call, "products")
    L, res = run(vendors, products, a.apply, a.limit, a.vendor)
    print("\n".join(L))
    print("%-34s %6s %6s %6s %6s  %s" % ("Lieferant", "Prod.", "Var.", "im Pr.", "fehlt", "Status"))
    for r in res["plan"]["rows"]:
        print("%-34s %6d %6d %6d %6d  %s" % (r["vendor"][:34], r["produkte"], r["varianten"], r["im_projekt"], r["fehlt"], r["status"]))
    return 1 if res["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
