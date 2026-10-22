"""Smilodox PO-ID je Bestellung im Lifecycle-PLM (eigenes Order-Custom-Field 'Smilodox PO-ID', dbKey mvjiwdeln1nssj_smilodox_po_id).
PO-ID = 'PO' + JJ (Jahr createdAt, Europe/Berlin) + '-' + PLM-orderNumber dreistellig, z. B. #36 aus 2026 -> PO26-036.
Das Feld poNumber (Lieferantennummer) wird NIE geaendert. Bestehende Werte werden nie ueberschrieben. Testbestellungen (ZZ..., T1-, TEST) werden ausgelassen.
Feld anlegen: GraphQL createMaterialCustomField(input{type:'ORDERS', fieldType:'INPUT', ...}) (Order-Custom-Fields laufen in der App ueber die Material-Custom-Field-API mit type ORDERS)."""
import datetime as dt
import json
import re
import subprocess
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BROWSER = Path(__file__).resolve().parent / "browser"
FIELD_NAME = "Smilodox PO-ID"
DBKEY = "mvjiwdeln1nssj_smilodox_po_id"
PO_RE = re.compile(r"(?<![A-Za-z0-9])PO(\d{2})-(\d{3})(?!\d)", re.I)


def is_test(title):
    t = str(title or "")
    return bool(re.match(r"(?i)\s*zz", t) or re.search(r"(?i)T1-|TEST", t))


def _created(o):
    c = o.get("createdAt")
    if c is None:
        return None
    if isinstance(c, (int, float)) or str(c).isdigit():
        return dt.datetime.fromtimestamp(int(c) / 1000, ZoneInfo("Europe/Berlin"))
    return dt.datetime.fromisoformat(str(c).replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Berlin"))


def po_id(o):
    """PO-ID einer Order (dict mit orderNumber, createdAt) oder None."""
    d, n = _created(o), o.get("orderNumber")
    if d is None or n in (None, ""):
        return None
    return "PO%02d-%03d" % (d.year % 100, int(n))


def norm_po(s):
    m = PO_RE.search(str(s or ""))
    return "PO%s-%s" % (m.group(1), m.group(2)) if m else None


def find_po_ids(*texts):
    """Alle PO-ID-Muster in den Texten (normalisiert, ohne Dubletten)."""
    out = []
    for t in texts:
        for m in PO_RE.finditer(str(t or "")):
            v = "PO%s-%s" % (m.group(1), m.group(2))
            if v not in out:
                out.append(v)
    return out


def by_po_id(orders):
    """{PO-ID: order} (nur eindeutige, ohne Testbestellungen)."""
    d, bad = {}, set()
    for o in orders:
        p = po_id(o)
        if not p or is_test(o.get("title")):
            continue
        if p in d:
            bad.add(p)
        d[p] = o
    return {k: v for k, v in d.items() if k not in bad}


def order_for_text(orders, *texts):
    """Genau die Bestellung, deren PO-ID in den Texten steht (None bei keinem oder mehreren verschiedenen Treffern)."""
    idx = by_po_id(orders)
    hits = {idx[p]["id"]: idx[p] for p in find_po_ids(*texts) if p in idx}
    return list(hits.values())[0] if len(hits) == 1 else None


# ---------------- Browser (GraphQL) ----------------
_JS_HEAD = r'''
const N=v=>({kind:'Name',value:v}); const V=n=>({kind:'Variable',name:N(n)});
const c=window.__APOLLO_CLIENT__; const DBKEY=%s;
const parseSel=s=>{const t=s.match(/[{}]|\w+/g);let i=0;const rec=()=>{const out=[];while(i<t.length&&t[i]!=='}'){const n=t[i++];const f={kind:'Field',name:N(n),arguments:[]};if(t[i]==='{'){i++;f.selectionSet={kind:'SelectionSet',selections:rec()};i++;}out.push(f);}return out;};return rec();};
const SEL=`id title poNumber useCustomPoNumber status{ id status color order } totalCost currency totalNumberOfPieces orderNumber createdAt exFactoryExpectedDate exFactoryActualDate etdEstimatedDate etdActualDate invoiceAddress shipAddress notes useCustomInvoiceAddress useCustomShipAddress hideLifecycleFooter isMatrixMode hiddenPoColumns customFields lockedAt items { id name totalQuantity price cost unit product { id } component { id } variants { name color avatar variantId amounts { key quantity price cost sourceAmount sourceCurrency exchangeRate rateAsOf conversionMode } } materialsSnapshot { lineId variantId name sku libraryId category color colorHex vendor vendorId buyer perPieceQty perPieceUnit orderedQty unit cost costUnit totalCost } } payments { id name status amount dueDate terms } assignees { id } manufacturer { id }`;
const getDoc={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'query',variableDefinitions:[{kind:'VariableDefinition',variable:V('id'),type:{kind:'NonNullType',type:{kind:'NamedType',name:N('String')}}}],selectionSet:{kind:'SelectionSet',selections:[{kind:'Field',name:N('getOrderById'),arguments:[{kind:'Argument',name:N('id'),value:V('id')}],selectionSet:{kind:'SelectionSet',selections:parseSel(SEL)}}]}}]};
const updDoc={kind:'Document',definitions:[{kind:'OperationDefinition',operation:'mutation',name:N('UpdateOrder'),variableDefinitions:[{kind:'VariableDefinition',variable:V('id'),type:{kind:'NonNullType',type:{kind:'NamedType',name:N('String')}}},{kind:'VariableDefinition',variable:V('data'),type:{kind:'NonNullType',type:{kind:'NamedType',name:N('OrderInput')}}}],selectionSet:{kind:'SelectionSet',selections:[{kind:'Field',name:N('updateOrder'),arguments:[{kind:'Argument',name:N('id'),value:V('id')},{kind:'Argument',name:N('orderInput'),value:V('data')}],selectionSet:{kind:'SelectionSet',selections:parseSel('id customFields')}}]}}]};
const clean=a=>JSON.parse(JSON.stringify(a,(k,v)=>(k==='__typename'?undefined:v)));
const fetchO=async id=>{const r=await c.query({query:getDoc,variables:{id},fetchPolicy:'no-cache',errorPolicy:'all'});return r.data&&r.data.getOrderById;};
const strip=o=>{const x=clean(o);delete x.customFields;delete x.lockedAt;return JSON.stringify(x);};   // alles ausser customFields muss unveraendert bleiben
''' % json.dumps(DBKEY)

JS_READ = "(async()=>{" + _JS_HEAD + r'''
const out={};
for(const id of __IDS__){try{const o=await fetchO(id);if(o)out[id]={v:(o.customFields||{})[DBKEY]||null,n:o.orderNumber,c:o.createdAt,t:o.title,p:o.poNumber,lock:o.lockedAt||null};}catch(e){out[id]={err:String(e.message).slice(0,150)};}}
return out;})()'''

# jobs: [{id, value}]. Schreibt customFields[DBKEY]=value (bestehende customFields bleiben, bestehender Wert wird nie ueberschrieben), liest zurueck und vergleicht den Rest der Order.
JS_SET = "(async()=>{" + _JS_HEAD + r'''
const out=[];
for(const j of __JOBS__){
  try{
    const o=await fetchO(j.id); if(!o){out.push({id:j.id,err:'nicht gefunden'});continue;}
    const cf=Object.assign({},o.customFields||{});
    if(cf[DBKEY]&&String(cf[DBKEY]).trim()){out.push({id:j.id,skip:'hat Wert',v:cf[DBKEY]});continue;}
    cf[DBKEY]=j.value;
    const before=strip(o);
    const d=clean(o);
    const data={title:d.title,manufacturer:d.manufacturer&&d.manufacturer.id,currency:d.currency,totalCost:d.totalCost,totalNumberOfPieces:d.totalNumberOfPieces,notes:d.notes,poNumber:d.poNumber,useCustomPoNumber:d.useCustomPoNumber,
      exFactoryExpectedDate:d.exFactoryExpectedDate,exFactoryActualDate:d.exFactoryActualDate,etdEstimatedDate:d.etdEstimatedDate,etdActualDate:d.etdActualDate,invoiceAddress:d.invoiceAddress,shipAddress:d.shipAddress,
      useCustomInvoiceAddress:d.useCustomInvoiceAddress,useCustomShipAddress:d.useCustomShipAddress,hideLifecycleFooter:d.hideLifecycleFooter,isMatrixMode:d.isMatrixMode,hiddenPoColumns:d.hiddenPoColumns,
      items:d.items.map(it=>Object.assign({},it,{product:it.product?it.product.id:undefined,component:it.component?it.component.id:undefined})),payments:d.payments,
      assignees:(d.assignees||[]).map(a=>a.id),status:d.status,customFields:cf};
    Object.keys(data).forEach(k=>{if(data[k]===null||data[k]===undefined)delete data[k];});
    data.items.forEach(it=>Object.keys(it).forEach(k=>{if(it[k]===null||it[k]===undefined)delete it[k];}));
    const r=await c.mutate({mutation:updDoc,variables:{id:j.id,data},errorPolicy:'all'});
    const err=(r.errors||[]).map(e=>e.message.slice(0,200));
    const a=await fetchO(j.id);
    out.push({id:j.id,err:err.length?err:null,v:a&&(a.customFields||{})[DBKEY],same:a?strip(a)===before:null,before:before});
  }catch(e){out.push({id:j.id,err:String(e.message).slice(0,200)});}
}
return out;})()'''


def run_js(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(BROWSER), timeout=1800)
    if r.returncode:
        raise RuntimeError("Browser-Lauf gescheitert: " + (r.stderr or r.stdout)[-300:])
    return json.loads(r.stdout)


def read_values(ids, runner=run_js):
    return runner(JS_READ.replace("__IDS__", json.dumps(list(ids)))) if ids else {}


def set_values(jobs, runner=run_js):
    return runner(JS_SET.replace("__JOBS__", json.dumps(jobs))) if jobs else []


def plan(orders, current):
    """orders: REST-Liste; current: {id: Wert|None} (aus read_values). -> (zu_schreiben [(order, po)], vorhanden_ok, abweichend [(order, soll, ist)], uebersprungen_test)."""
    todo, ok, wrong, skipped = [], [], [], []
    for o in sorted(orders, key=lambda x: (x.get("orderNumber") or 0)):
        if is_test(o.get("title")):
            skipped.append(o); continue
        p = po_id(o)
        if not p:
            continue
        cur = (current.get(o["id"]) or {}).get("v")
        if not cur:
            todo.append((o, p))
        elif cur == p:
            ok.append(o)
        else:
            wrong.append((o, p, cur))
    return todo, ok, wrong, skipped


def backfill(orders, apply=False, runner=run_js, only=None, log=None):
    """Nachtrag fuer alle Bestellungen ohne PO-ID. Gibt dict(todo, written, mismatches, errors, skipped_test, existing_other) zurueck."""
    ids = [o["id"] for o in orders if not is_test(o.get("title"))]
    cur = read_values(ids, runner)
    todo, ok, wrong, skipped = plan(orders, cur)
    if only:
        todo = [t for t in todo if t[0]["id"] in only]
    res = {"todo": todo, "ok": len(ok), "existing_other": wrong, "skipped_test": skipped, "written": 0, "mismatches": [], "errors": []}
    if apply and todo:
        out = set_values([{"id": o["id"], "value": p} for o, p in todo], runner)
        bk = ROOT / "output" / "backup" / ("orders_before_po_ids_%s.json" % dt.date.today().isoformat())   # Stand vor dem Schreiben (ohne customFields), nur anhaengen
        old = json.load(open(bk)) if bk.exists() else {}
        old.update({r["id"]: json.loads(r["before"]) for r in out if r.get("before") and r["id"] not in old})
        bk.parent.mkdir(parents=True, exist_ok=True); json.dump(old, open(bk, "w"), ensure_ascii=False)
        want = {o["id"]: (o, p) for o, p in todo}
        for r in out:
            o, p = want[r["id"]]
            if r.get("err") or r.get("skip"):
                res["errors"].append((o.get("title"), r.get("err") or r.get("skip"))); continue
            if r.get("v") != p:
                res["mismatches"].append((o.get("title"), p, r.get("v")))
            elif r.get("same") is False:
                res["mismatches"].append((o.get("title"), "Rest der Bestellung veraendert", ""))
            else:
                res["written"] += 1
    return res


def ensure_after_create(order_id, orders_hint=None, runner=run_js):
    """Nach dem Anlegen einer Bestellung: PO-ID aus orderNumber/createdAt setzen und zurueckgelesen pruefen. -> (po, ok, info)."""
    cur = read_values([order_id], runner).get(order_id) or {}
    if cur.get("err") or "n" not in cur:
        return None, False, cur.get("err") or "Bestellung nicht lesbar"
    po = po_id({"orderNumber": cur["n"], "createdAt": cur["c"]})
    if cur.get("v"):
        return po, cur["v"] == po, "vorhanden: %s" % cur["v"]
    r = (set_values([{"id": order_id, "value": po}], runner) or [{}])[0]
    return po, (r.get("v") == po and r.get("same") is not False and not r.get("err")), r.get("err") or ""


STATE_NAME = "po_ids.json"


def auto(intake, created_titles, apply, call=None, runner=run_js, today=None):
    """Fuer auto_run (nur apply): (a) frisch angelegte Bestellungen (Titel) sofort mit PO-ID versehen und zuruecklesen, (b) einmal taeglich Nachtrag fuer alle Bestellungen ohne PO-ID
    (z. B. manuell angelegte). Merker <intake>/po_ids.json. -> Berichtszeilen."""
    if not apply:
        return ["- (Trockenlauf) nichts geschrieben"]
    import plm_client
    from plm_intake.context import fetch_all
    st_path = Path(intake) / STATE_NAME
    st = json.load(open(st_path)) if st_path.exists() else {}
    today = today or dt.date.today().isoformat()
    daily = st.get("last_backfill") != today
    if not created_titles and not daily:
        return ["- nichts zu tun (Nachtrag heute schon gelaufen)"]
    orders = fetch_all(call or plm_client.call, "orders")
    only = None
    if created_titles and not daily:
        only = {o["id"] for o in orders if o.get("title") in set(created_titles)}
    res = backfill(orders, apply=True, runner=runner, only=only)
    bad = res["mismatches"] + res["errors"]
    if daily and not bad:
        st["last_backfill"] = today; json.dump(st, open(st_path, "w"))
    L = ["- geschrieben %d (neu angelegt: %d), Fehler/Abweichungen nach Zuruecklesen: %d" % (res["written"], len(created_titles or []), len(bad))]
    L += ["- PROBLEM %s" % (b,) for b in bad[:5]]
    return L


def supplier_md(orders, numbers, today=None):
    """Vorlage zum Verschicken: je Lieferant die offenen Bestellungen (Status nicht Complete) mit PO-ID, Titel, Lieferanten-Nummer (poNumber)."""
    by = {}
    for o in orders:
        if is_test(o.get("title")) or str((o.get("status") or {}).get("status") or "").lower() == "complete":
            continue
        by.setdefault((o.get("manufacturer") or {}).get("name") or "(ohne Lieferant)", []).append(o)
    L = ["# Smilodox PO-IDs je Lieferant (offene Bestellungen)", "", "Stand %s. Bitte nennt uns auf Belegen (PI, Rechnung, Packliste) und in Mails die **Smilodox PO-ID** (Format POJJ-NNN). Die Lieferanten-Nummer bleibt unveraendert." % (today or dt.date.today().isoformat()), ""]
    for v in sorted(by, key=str.lower):
        L += ["## " + v, "", "| Smilodox PO-ID | Titel | Lieferanten-Nummer (poNumber) | Status |", "|---|---|---|---|"]
        for o in sorted(by[v], key=lambda x: x.get("orderNumber") or 0):
            L.append("| %s | %s | %s | %s |" % (po_id(o), o.get("title"), numbers.get(o["id"]) or "-", (o.get("status") or {}).get("status")))
        L.append("")
    return "\n".join(L)


def main(argv=None):
    import argparse
    import plm_client
    from plm_intake.context import fetch_all
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    orders = fetch_all(plm_client.call, "orders")
    outd = ROOT / "output" / "phase2" / "B18"; outd.mkdir(parents=True, exist_ok=True)
    res = backfill(orders, apply=a.apply)
    # Nach dem Schreiben alles zurueckgelesen
    real = [o for o in orders if not is_test(o.get("title"))]
    cur = read_values([o["id"] for o in real])
    bad = [(o.get("title"), po_id(o), (cur.get(o["id"]) or {}).get("v")) for o in real if (cur.get(o["id"]) or {}).get("v") != po_id(o)]
    L = ["# PO-IDs (%s)" % ("geschrieben" if a.apply else "Trockenlauf"), "", "Feld 'Smilodox PO-ID' (dbKey %s). Testbestellungen ausgelassen: %d. Bereits korrekt vorher: %d. Geschrieben: %d." % (DBKEY, len(res["skipped_test"]), res["ok"], res["written"]), "",
         "| Titel | # | PO-ID | Wert im PLM |", "|---|---|---|---|"]
    for o in sorted(real, key=lambda x: x.get("orderNumber") or 0):
        L.append("| %s | %s | %s | %s |" % (o.get("title"), o.get("orderNumber"), po_id(o), (cur.get(o["id"]) or {}).get("v") or "-"))
    L += ["", "## Zurueckgelesen: Abweichungen", ""] + (["- %s: soll %s, ist %s" % b for b in bad] or ["- keine (alle Werte stimmen)" if a.apply else "- (Trockenlauf)"])
    L += ["", "## Fehler beim Schreiben", ""] + (["- %s: %s" % e for e in res["errors"]] or ["- keine"])
    (outd / "po_ids.md").write_text("\n".join(L) + "\n")
    numbers = {k: v.get("p") for k, v in cur.items() if isinstance(v, dict)}
    (outd / "po_ids_je_lieferant.md").write_text(supplier_md(orders, numbers) + "\n")
    print("todo %d, geschrieben %d, abweichend %d, Fehler %d" % (len(res["todo"]), res["written"], len(bad), len(res["errors"])))
    return 1 if bad or res["errors"] or res["mismatches"] else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
