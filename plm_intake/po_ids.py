"""Smilodox PO-ID je Bestellung im Lifecycle-PLM (eigenes Order-Custom-Field 'Smilodox PO-ID', dbKey mvjiwdeln1nssj_smilodox_po_id).
NEU (29.10.2026): PO-ID = 'PO-' + 3-Buchstaben-Kuerzel des Lieferanten + '-' + laufende Nummer je Lieferant (zweistellig, ab 100 dreistellig), z. B. PO-LIEFERANT_AA-05.
Die Zuordnung Bestellung -> PO-ID steht dauerhaft in <intake>/po_ids.json (Schluessel 'ids'): einmal vergeben, nie neu gezaehlt (auch nicht nach Loeschungen); neue Bestellungen bekommen hoechste Nummer + 1.
Altes Format (nur solange keine Registry aktiv ist, und als weiter erkanntes Alias): 'PO' + JJ (Jahr createdAt, Europe/Berlin) + '-' + PLM-orderNumber dreistellig, z. B. #36 aus 2026 -> PO26-036.
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
PO_RE = re.compile(r"(?<![A-Za-z0-9])PO(\d{2})-(\d{3})(?!\d)", re.I)   # altes Format PO26-036 (wird weiter erkannt)
NEW_RE = re.compile(r"(?<![A-Za-z0-9])PO-([A-Z]{3})-(\d{1,3})(?![A-Za-z0-9])", re.I)   # neues Format PO-LIEFERANT_AA-05
REGISTRY = None   # {order_id: 'PO-LIEFERANT_AA-05'}; None = altes Format (nur Tests/Altcode)
STATE_NAME = "po_ids.json"


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


def legacy_id(o):
    """Altes Format PO26-036 (Jahr + PLM-orderNumber) oder None."""
    d, n = _created(o), o.get("orderNumber")
    if d is None or n in (None, ""):
        return None
    return "PO%02d-%03d" % (d.year % 100, int(n))


def fmt(code, n):
    return "PO-%s-%02d" % (code.upper(), int(n))


def po_id(o):
    """PO-ID einer Order: mit aktiver Registry PO-LIEFERANT_AA-05 (None, wenn die Bestellung keine hat), sonst altes Format."""
    if REGISTRY is not None:
        return REGISTRY.get(o.get("id"))
    return legacy_id(o)


def set_registry(reg):
    global REGISTRY
    REGISTRY = None if reg is None else dict(reg)


def _norm_new(m):
    return fmt(m.group(1), m.group(2))


def norm_po(s):
    t = str(s or "")
    m = NEW_RE.search(t)
    if m:
        return _norm_new(m)
    m = PO_RE.search(t)
    return "PO%s-%s" % (m.group(1), m.group(2)) if m else None


def find_po_ids(*texts):
    """Alle PO-ID-Muster (neu PO-LIEFERANT_AA-05 und alt PO26-036) in den Texten (normalisiert, ohne Dubletten)."""
    out = []
    for t in texts:
        t = str(t or "")
        found = [(m.start(), _norm_new(m)) for m in NEW_RE.finditer(t)] + [(m.start(), "PO%s-%s" % (m.group(1), m.group(2))) for m in PO_RE.finditer(t)]
        for _, v in sorted(found):
            if v not in out:
                out.append(v)
    return out


def load_codes(intake):
    """{Hersteller-ID: 3-Buchstaben-Kuerzel} aus <intake>/lieferanten_ids.json (im PLM gesetzte Werte, sonst zugeordnete)."""
    try:
        d = json.load(open(Path(intake) / "lieferanten_ids.json"))
    except Exception:
        return {}
    codes = {k: v.get("code") for k, v in (d.get("zugeordnet") or {}).items() if isinstance(v, dict) and v.get("code")}
    codes.update({k: v for k, v in (d.get("im_plm") or {}).items() if v})
    return {k: str(v).upper() for k, v in codes.items() if re.fullmatch(r"[A-Za-z]{3}", str(v))}


def assign(orders, codes, reg):
    """Vergibt PO-IDs an Bestellungen ohne Eintrag: je Lieferant hoechste Nummer + 1 (nach PLM-Nummer aufsteigend). Testbestellungen und Bestellungen ohne Lieferanten-Kuerzel bekommen keine.
    -> (neue Registry, [Titel ohne Kuerzel])"""
    reg = dict(reg or {})
    top = {}
    for p in reg.values():
        m = NEW_RE.fullmatch(p)
        if m:
            top[m.group(1).upper()] = max(top.get(m.group(1).upper(), 0), int(m.group(2)))
    missing = []
    for o in sorted(orders, key=lambda x: (x.get("orderNumber") or 0, str(x.get("createdAt")))):
        if o.get("id") in reg or is_test(o.get("title")):
            continue
        code = codes.get((o.get("manufacturer") or {}).get("id"))
        if not code:
            missing.append(o.get("title")); continue
        top[code] = top.get(code, 0) + 1
        reg[o["id"]] = fmt(code, top[code])
    return reg, missing


def activate(intake, orders, save=True):
    """Registry laden, neue Bestellungen ergaenzen, (bei save) dauerhaft speichern und aktiv schalten. -> (Registry, [Titel ohne Kuerzel], Anzahl neu)."""
    path = Path(intake) / STATE_NAME
    try:
        st = json.load(open(path))
    except Exception:
        st = {}
    reg, missing = assign(orders, load_codes(intake), st.get("ids") or {})
    new = len(reg) - len(st.get("ids") or {})
    if save and new:
        st["ids"] = reg
        path.parent.mkdir(parents=True, exist_ok=True)
        json.dump(st, open(path, "w"), ensure_ascii=False, indent=1, sort_keys=True)
    set_registry(reg)
    return reg, missing, new


def by_po_id(orders):
    """{PO-ID: order} (nur eindeutige, ohne Testbestellungen)."""
    d, bad = {}, set()
    for o in orders:
        if is_test(o.get("title")):
            continue
        for p in {po_id(o), legacy_id(o) if REGISTRY is not None else None} - {None}:
            if p in d and d[p] is not o:
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

# jobs: [{id, value, force?}]. Schreibt customFields[DBKEY]=value (bestehende customFields bleiben; ein bestehender Wert wird nur mit force ueberschrieben, dann steht der alte in 'old'), liest zurueck und vergleicht den Rest der Order.
JS_SET = "(async()=>{" + _JS_HEAD + r'''
const out=[];
for(const j of __JOBS__){
  try{
    const o=await fetchO(j.id); if(!o){out.push({id:j.id,err:'nicht gefunden'});continue;}
    const cf=Object.assign({},o.customFields||{});
    if(!j.force&&cf[DBKEY]&&String(cf[DBKEY]).trim()){out.push({id:j.id,skip:'hat Wert',v:cf[DBKEY]});continue;}
    const old=cf[DBKEY]||null;
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
    out.push({id:j.id,err:err.length?err:null,v:a&&(a.customFields||{})[DBKEY],same:a?strip(a)===before:null,before:before,old:old});
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
        if not cur or (REGISTRY is not None and PO_RE.fullmatch(str(cur).strip())):   # leer oder altes Format -> neu schreiben
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
        out = set_values([{"id": o["id"], "value": p, "force": bool((cur.get(o["id"]) or {}).get("v"))} for o, p in todo], runner)
        bk = ROOT / "output" / "backup" / ("orders_before_po_ids_%s.json" % dt.date.today().isoformat())   # Stand vor dem Schreiben (ohne customFields), nur anhaengen
        old = json.load(open(bk)) if bk.exists() else {}
        old.update({r["id"]: json.loads(r["before"]) for r in out if r.get("before") and r["id"] not in old})
        bk.parent.mkdir(parents=True, exist_ok=True); json.dump(old, open(bk, "w"), ensure_ascii=False)
        bk2 = ROOT / "output" / "backup" / ("po_ids_alte_werte_%s.json" % dt.date.today().isoformat())   # alte PO-ID-Werte vor dem Ueberschreiben
        o2 = json.load(open(bk2)) if bk2.exists() else {}
        o2.update({r["id"]: r["old"] for r in out if r.get("old") and r["id"] not in o2})
        if o2:
            json.dump(o2, open(bk2, "w"), ensure_ascii=False, indent=1)
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
    reg, missing, new = activate(intake, orders, save=True)
    only = None
    if created_titles and not daily:
        only = {o["id"] for o in orders if o.get("title") in set(created_titles)}
    res = backfill(orders, apply=True, runner=runner, only=only)
    bad = res["mismatches"] + res["errors"]
    if daily and not bad:
        st["last_backfill"] = today; json.dump(st, open(st_path, "w"))
    L = ["- geschrieben %d (neu angelegt: %d), Fehler/Abweichungen nach Zuruecklesen: %d" % (res["written"], len(created_titles or []), len(bad))]
    if missing:
        L.append("- ohne PO-ID (Lieferanten-Kuerzel fehlt): %s" % ", ".join(str(m) for m in missing[:8]))
    L += ["- PROBLEM %s" % (b,) for b in bad[:5]]
    return L


def supplier_md(orders, numbers, today=None):
    """Vorlage zum Verschicken: je Lieferant die offenen Bestellungen (Status nicht Complete) mit PO-ID, Titel, Lieferanten-Nummer (poNumber)."""
    by = {}
    for o in orders:
        if is_test(o.get("title")) or str((o.get("status") or {}).get("status") or "").lower() == "complete":
            continue
        by.setdefault((o.get("manufacturer") or {}).get("name") or "(ohne Lieferant)", []).append(o)
    L = ["# Smilodox PO-IDs je Lieferant (offene Bestellungen)", "", "Stand %s. Bitte nennt uns auf Belegen (PI, Rechnung, Packliste) und in Mails die **Smilodox PO-ID** (Format PO-XXX-NN, z. B. PO-LIEFERANT_AA-05). Die Lieferanten-Nummer bleibt unveraendert." % (today or dt.date.today().isoformat()), ""]
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
    activate(ROOT / "output" / "intake", orders, save=a.apply)
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
