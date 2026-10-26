"""Lieferanten-Projekte im Lifecycle-PLM: je Lieferant (manufacturer) mit mindestens einer echten Order ODER mindestens 5 echten Produkten (Main Vendor) ein Projekt (Name exakt = Lieferantenname);
jede echte Order ohne Projektverknuepfung wird mit dem Projekt ihres Lieferanten verknuepft.

Regeln: Test-Orders (ZZ-/T1-/TEST-Titel) zaehlen nicht. Eine Order hoechstens in EINEM Projekt; vorhandene Verknuepfungen werden nie geaendert oder geloest.
Projekte werden per normalisiertem Namen wiedergefunden (keine Duplikate; bei mehreren gleichnamigen Projekten Warnung, nichts geraten).
Order ohne erkennbaren Lieferanten: Warnung, keine Verknuepfung. Max. MAX_LINKS Verknuepfungen und MAX_CREATES neue Projekte pro Lauf.
Schreiben per App-GraphQL im Browser (wie po_ids): createProject(createProjectInput{name}), linkOrderToProject(input{projectId, orderId, notes}).
Nach dem Schreiben wird zurueckgelesen (linkedOrders des Projekts enthaelt die Order). Vorzustand: output/backup/vendor_projects_vor_<Zeit>.json.
Dry-Run ist Standard:  python3 -m plm_intake.vendor_projects [--apply]"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSER = Path(__file__).resolve().parent / "browser"
BACKUP_DIR = ROOT / "output" / "backup"
MAX_LINKS = 30
MAX_CREATES = 30
LINK_NOTE = "Linked from project interface"


def is_test(title):
    t = str(title or "")
    return bool(re.search(r"(?i)(^|[^a-z0-9])zz|(^|[^a-z0-9])T1([^a-z0-9]|$)|TEST", t))


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "").casefold().replace("ı", "i")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s)


def order_vendor_id(o):
    m = o.get("manufacturer")
    if isinstance(m, dict):
        return m.get("id") or m.get("_id")
    return m or o.get("manufacturerId") or None


def plan(vendors, orders, projects, max_links=MAX_LINKS, max_creates=MAX_CREATES, product_vendors=()):
    """Reine Planung. projects: [{id,name,linkedOrders:[{_id,orderId}]}]. -> dict create/links/warnings/vendors_ohne_projekt/orders_ohne_projekt/..."""
    vname = {v["id"]: v.get("name") or "" for v in vendors}
    linked = {}   # orderId -> Projekt-ID (jede Verknuepfung, egal in welchem Projekt)
    by_name = {}
    for p in projects:
        by_name.setdefault(norm(p.get("name")), []).append(p)
        for lo in p.get("linkedOrders") or []:
            linked.setdefault(str(lo.get("orderId")), p["id"])
    warnings, no_vendor, open_orders = [], [], []
    vendors_with_orders = {}
    for o in orders:
        if is_test(o.get("title")):
            continue
        vid = order_vendor_id(o)
        if vid in vname and re.match(r"(?i)\s*zz", vname[vid]):
            continue   # Test-Lieferant
        if not vid or vid not in vname or not norm(vname[vid]):
            no_vendor.append(o)
            warnings.append("Order ohne erkennbaren Lieferanten, nicht verknuepft: %s" % o.get("title"))
            continue
        vendors_with_orders.setdefault(vid, []).append(o)
        if str(o["id"]) not in linked:
            open_orders.append((vid, o))
    proj_for, ohne_projekt, create = {}, [], []
    # Lieferanten mit genuegend Produkten (product_vendors, vom Aufrufer berechnet) bekommen auch ohne Bestellung ein Projekt
    need = set(vendors_with_orders) | {v for v in product_vendors if v in vname and norm(vname[v]) and not re.match(r"(?i)\s*zz", vname[v])}
    for vid in sorted(need, key=lambda v: vname[v].casefold()):
        hit = by_name.get(norm(vname[vid]), [])
        if len(hit) > 1:
            warnings.append("Mehrere Projekte mit Namen '%s' (%s), Lieferant uebersprungen" % (vname[vid], ", ".join(p["id"] for p in hit)))
            proj_for[vid] = "AMBIGUOUS"
        elif hit:
            proj_for[vid] = hit[0]["id"]
        else:
            ohne_projekt.append(vname[vid])
            if len(create) < max_creates:
                create.append(vname[vid]); proj_for[vid] = None
            else:
                proj_for[vid] = "OVER"
    links, offen_limit = [], []
    for vid, o in open_orders:
        pid = proj_for.get(vid)
        if pid in ("AMBIGUOUS", "OVER"):
            offen_limit.append(o["title"]); continue
        if len(links) >= max_links:
            offen_limit.append(o["title"]); continue
        links.append({"order_id": o["id"], "title": o.get("title"), "vendor": vname[vid], "project_id": pid})
    if offen_limit:
        warnings.append("%d Order(s) erst im naechsten Lauf (Limit/Mehrdeutigkeit): %s" % (len(offen_limit), ", ".join(map(str, offen_limit[:6]))))
    return {"create": create, "links": links, "warnings": warnings, "vendors_ohne_projekt": ohne_projekt,
            "orders_ohne_projekt": [{"title": o.get("title"), "vendor": vname[v]} for v, o in open_orders], "no_vendor": [o.get("title") for o in no_vendor]}


# ---------------- Browser (GraphQL) ----------------
_HEAD = r'''
const N=v=>({kind:'Name',value:v}); const V=n=>({kind:'Variable',name:N(n)});
const c=window.__APOLLO_CLIENT__;
const parseSel=s=>{const t=s.match(/[{}]|\w+/g);let i=0;const rec=()=>{const out=[];while(i<t.length&&t[i]!=='}'){const n=t[i++];const f={kind:'Field',name:N(n),arguments:[]};if(t[i]==='{'){i++;f.selectionSet={kind:'SelectionSet',selections:rec()};i++;}out.push(f);}return out;};return rec();};
const nn=t=>({kind:'NonNullType',type:{kind:'NamedType',name:N(t)}});
const doc=(op,vars,field,args,sel)=>({kind:'Document',definitions:[{kind:'OperationDefinition',operation:op,variableDefinitions:vars.map(([n,t])=>({kind:'VariableDefinition',variable:V(n),type:nn(t)})),
  selectionSet:{kind:'SelectionSet',selections:[{kind:'Field',name:N(field),arguments:args,selectionSet:{kind:'SelectionSet',selections:parseSel(sel)}}]}}]});
const PSEL='id name linkedOrders { _id orderId linkedAt notes }';
const readProjects=async()=>{const d={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'query',selectionSet:{kind:'SelectionSet',selections:[{kind:'Field',name:N('projects'),
  arguments:[{kind:'Argument',name:N('limit'),value:{kind:'IntValue',value:'1000'}}],selectionSet:{kind:'SelectionSet',selections:parseSel(PSEL)}}]}}]};
  const r=await c.query({query:d,fetchPolicy:'no-cache',errorPolicy:'all'});
  return {data:r.data&&r.data.projects,err:(r.errors||[]).map(e=>e.message.slice(0,200))};};
const clean=a=>JSON.parse(JSON.stringify(a,(k,v)=>(k==='__typename'?undefined:v)));
'''

JS_READ = "(async()=>{" + _HEAD + "const r=await readProjects(); return {projects:r.data?clean(r.data):null,err:r.err};})()"

JS_WRITE = "(async()=>{" + _HEAD + r'''
const createDoc=doc('mutation',[['name','String']],'createProject',[{kind:'Argument',name:N('createProjectInput'),value:{kind:'ObjectValue',fields:[{kind:'ObjectField',name:N('name'),value:V('name')}]}}],'id name');
const linkDoc=doc('mutation',[['input','LinkOrderToProjectInput']],'linkOrderToProject',[{kind:'Argument',name:N('input'),value:V('input')}],PSEL);
const out={created:[],links:[],stop:null};
const idByName={};
for(const nm of __CREATE__){
  try{
    const r=await c.mutate({mutation:createDoc,variables:{name:nm},errorPolicy:'all'});
    const err=(r.errors||[]).map(e=>e.message.slice(0,200));
    const p=r.data&&r.data.createProject;
    if(p&&p.id&&!err.length){idByName[nm]=p.id;out.created.push({name:nm,id:p.id});}
    else{out.created.push({name:nm,err:err.length?err:'keine ID'});out.stop='Projekt anlegen fehlgeschlagen: '+nm;break;}
  }catch(e){out.created.push({name:nm,err:String(e.message).slice(0,200)});out.stop='Projekt anlegen unsicher: '+nm;break;}
}
if(!out.stop){
for(const j of __LINKS__){
  const pid=j.project_id||idByName[j.project_name];
  if(!pid){out.links.push({order:j.order_id,err:'Projekt unbekannt'});continue;}
  try{
    const r=await c.mutate({mutation:linkDoc,variables:{input:{projectId:pid,orderId:j.order_id,notes:__NOTE__}},errorPolicy:'all'});
    const err=(r.errors||[]).map(e=>e.message.slice(0,200));
    const p=r.data&&r.data.linkOrderToProject;
    out.links.push({order:j.order_id,project:pid,err:err.length?err:null,inResponse:!!(p&&(p.linkedOrders||[]).some(l=>String(l.orderId)===String(j.order_id)))});
    if(err.length){out.stop='Verknuepfen fehlgeschlagen: '+j.order_id;break;}
  }catch(e){out.links.push({order:j.order_id,project:pid,err:String(e.message).slice(0,200)});out.stop='Verknuepfen unsicher: '+j.order_id;break;}
}}
const after=await readProjects();
out.after=after.data?clean(after.data):null; out.afterErr=after.err;
return out;})()'''


def run_js(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(BROWSER), timeout=1800)
    if r.returncode:
        raise RuntimeError("Browser-Lauf gescheitert: " + (r.stderr or r.stdout)[-300:])
    return json.loads(r.stdout)


def read_projects(runner=run_js):
    res = runner(JS_READ)
    if res.get("projects") is None:
        raise RuntimeError("Projekte nicht lesbar: %s" % res.get("err"))
    return res["projects"]


def write(pl, runner=run_js):
    js = (JS_WRITE.replace("__CREATE__", json.dumps(pl["create"])).replace("__LINKS__", json.dumps([dict(l, project_name=l["vendor"]) for l in pl["links"]]))
          .replace("__NOTE__", json.dumps(LINK_NOTE)))
    return runner(js)


def verify(pl, res):
    """Zuruecklesen: je geplanter Verknuepfung muss die Order in linkedOrders genau EINES Projekts stehen, und zwar im Projekt des Lieferanten. -> (verknuepft, fehler[])"""
    after = res.get("after")
    if after is None:
        return 0, ["Zuruecklesen der Projekte fehlgeschlagen: %s" % res.get("afterErr")]
    where = {}
    for p in after:
        for lo in p.get("linkedOrders") or []:
            where.setdefault(str(lo.get("orderId")), []).append(p)
    done = {str(l.get("order")): l for l in res.get("links") or []}
    ok, errs = 0, []
    for c in res.get("created") or []:
        if c.get("err"):
            errs.append("Projekt '%s' nicht angelegt: %s" % (c.get("name"), c["err"]))
    for l in pl["links"]:
        w = where.get(str(l["order_id"]), [])
        d = done.get(str(l["order_id"]))
        if d is None:
            errs.append("%s: nicht versucht (Lauf gestoppt: %s)" % (l["title"], res.get("stop")))
        elif d.get("err"):
            errs.append("%s: %s" % (l["title"], d["err"]))
        elif len(w) != 1 or norm(w[0].get("name")) != norm(l["vendor"]):
            errs.append("%s: Zuruecklesen unstimmig (Projekte: %s)" % (l["title"], [p.get("name") for p in w]))
        else:
            ok += 1
    return ok, errs


def backup(projects, pl, now=None):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    p = BACKUP_DIR / ("vendor_projects_vor_%s.json" % (now or dt.datetime.now()).strftime("%Y-%m-%d_%H%M%S"))
    p.write_text(json.dumps({"projects": projects, "plan": pl}, ensure_ascii=False, indent=1))
    return p


def run(vendors, orders, apply=False, runner=run_js, backup_fn=backup, product_vendors=()):
    """-> (zeilen, ergebnis{neu,verknuepft,fehler,warnungen,plan}). Trockenlauf liest nur."""
    projects = read_projects(runner)
    pl = plan(vendors, orders, projects, product_vendors=product_vendors)
    res = {"neu": 0, "verknuepft": 0, "fehler": 0, "warnungen": list(pl["warnings"]), "plan": pl}
    L = ["- Projekte im PLM: %d | Lieferanten ohne Projekt: %d | Orders ohne Projekt: %d | geplant: %d neue Projekte, %d Verknuepfungen" % (
        len(projects), len(pl["vendors_ohne_projekt"]), len(pl["orders_ohne_projekt"]), len(pl["create"]), len(pl["links"]))]
    L += ["- WARNUNG %s" % w for w in pl["warnings"]]
    if not apply:
        return ["- (Trockenlauf) nichts geschrieben"] + L, res
    if not pl["create"] and not pl["links"]:
        return L + ["- nichts zu tun"], res
    L.append("- Backup: %s" % backup_fn(projects, pl))
    out = write(pl, runner)
    ok, errs = verify(pl, out)
    new_names = [c["name"] for c in out.get("created") or [] if c.get("id")]
    res.update(neu=len(new_names), verknuepft=ok, fehler=len(errs))
    L.append("- Projekte: neu %d, verknuepft %d, Fehler %d" % (res["neu"], ok, len(errs)))
    L += ["- FEHLER %s" % e for e in errs[:8]]
    res["warnungen"] += ["Projekte/Verknuepfung: %s" % e for e in errs[:5]]
    return L, res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    import plm_client
    from plm_intake.context import fetch_all
    from plm_intake import vendor_project_products as vpp
    vendors, orders = fetch_all(plm_client.call, "vendors"), fetch_all(plm_client.call, "orders")
    pv = vpp.vendors_needing_project(vendors, fetch_all(plm_client.call, "products"))
    L, res = run(vendors, orders, a.apply, product_vendors=pv)
    print("\n".join(L))
    if not a.apply:
        pl = res["plan"]
        print("Lieferanten ohne Projekt (%d): %s" % (len(pl["vendors_ohne_projekt"]), "; ".join(pl["vendors_ohne_projekt"])))
        print("Orders ohne Projekt (%d):" % len(pl["orders_ohne_projekt"]))
        for o in pl["orders_ohne_projekt"]:
            print("  %s | %s" % (o["title"], o["vendor"]))
    return 1 if res["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
