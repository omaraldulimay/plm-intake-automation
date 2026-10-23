"""Smilodox Lieferanten-ID (3-Buchstaben-Kuerzel aus dem Stammdaten-Register, Blatt Lists, Spalte 'Supplier ID') je Lieferant im Lifecycle-PLM.
Eigenes Vendor-Custom-Field 'Smilodox Lieferanten-ID' (materialCustomFields type 'VENDOR', Typ INPUT); Wert liegt in manufacturer.customFields[dbKey]
und wird per updateManufacturer(manufacturerId, manufacturerInput{customFields}) gesetzt (Browser/Apollo wie po_ids.py).

WICHTIG: Das Register enthaelt nur die Kuerzel, KEINE Namen. Die Zuordnung Kuerzel -> PLM-Lieferant wird deshalb aus dem Kuerzel abgeleitet
(Buchstaben in Reihenfolge im Namen, erster Buchstabe = Anfang eines Namensteils) und nur geschrieben, wenn sie eindeutig ist:
Kuerzel hat genau einen Kandidaten UND der Lieferant genau ein Kuerzel (nach Ausschluss bereits eindeutig vergebener). Sonst: Liste 'mehrdeutig/ohne Kuerzel', nichts geschrieben.
Bestehende Werte werden nie ueberschrieben. Das Kuerzel dient NIE allein zur Zuordnung einer Bestellung (nur schwaches Zusatzsignal, siehe signal_for_text)."""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "output" / "phase2" / "B19"
REGISTER = OUTDIR / "register_codes.json"
FIELD_NAME = "Smilodox Lieferanten-ID"
FIELD_TYPE = "VENDOR"
BRAND_ID = "6a1d319af153cb35c5b31dfe"
STATE_NAME = "vendor_ids.json"
FIELD_KEY_FILE = OUTDIR / "feld.json"     # {"dbKey":..., "id":...} nach dem Anlegen

STOP = {"CO", "LTD", "LIMITED", "GMBH", "SAN", "VE", "DIS", "TIC", "STI", "PVT", "THE", "OF", "AND", "INDUSTRY", "TRADING", "TEXTILE", "TEXTILES", "TEKSTIL",
        "SPORTS", "COMPANY", "GARMENT", "INTERNATIONAL", "TRADE", "IMP", "EXP", "APPAREL", "GROUP", "ENTERPRISES", "HOUSEWARES", "WORLDWIDE"}
SKIP_NAME = re.compile(r"^(ZZ|Default Vendor|SPEDITION_B )", re.I)    # Tests, Standard-Vendor, Logistiker


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "").replace("ı", "i").replace("ü", "u")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z ]", " ", s)


def _subseq(c, w):
    i = 0
    for ch in w:
        if i < len(c) and ch == c[i]:
            i += 1
    return i == len(c)


def candidate(code, name):
    """True, wenn das Kuerzel aus dem Namen ableitbar ist (Einzelwort oder Initialen/Teile der ersten Namensteile)."""
    c = code.upper()
    toks = fold(name).split()
    sig = [w for w in toks if w not in STOP]
    for w in sig:
        if len(w) >= 3 and w[0] == c[0] and _subseq(c, w):
            return True
    for n in (2, 3):
        parts = sig[:n]
        if len(parts) == n and parts[0][0] == c[0] and _subseq(c, "".join(parts)) and all(any(ch in w for ch in c[1:]) for w in parts[1:]):
            return True
    return False


def exact_token(code, name):
    return code.upper() in fold(name).split()


def load_codes(path=REGISTER):
    return list(json.load(open(path))["codes"])


def duplicates(codes):
    seen, dup = set(), []
    for c in codes:
        if c in seen and c not in dup:
            dup.append(c)
        seen.add(c)
    return dup


def assign(codes, vendors):
    """-> dict(zugeordnet {vendor_id: (code, name)}, mehrdeutig [(code, [namen])], ohne_kuerzel [vendor], ohne_vendor [code], doppelt [code])."""
    vs = [v for v in vendors if not SKIP_NAME.match(v.get("name") or "")]
    codes_u = list(dict.fromkeys(codes))
    cand = {}
    for c in codes_u:
        ex = [v for v in vs if exact_token(c, v["name"])]
        cand[c] = ex if ex else [v for v in vs if candidate(c, v["name"])]
    done, used_c, used_v = {}, set(), set()
    changed = True
    while changed:
        changed = False
        for c in codes_u:
            if c in used_c:
                continue
            opts = [v for v in cand[c] if v["id"] not in used_v]
            if len(opts) != 1:
                continue
            v = opts[0]
            # der Lieferant darf nicht noch von einem anderen, ebenfalls eindeutigen Kuerzel beansprucht werden
            rivals = [d for d in codes_u if d != c and d not in used_c and [x for x in cand[d] if x["id"] not in used_v] == [v]]
            if rivals:
                continue
            done[v["id"]] = (c, v["name"]); used_c.add(c); used_v.add(v["id"]); changed = True
    ambiguous = [(c, [v["name"] for v in cand[c] if v["id"] not in used_v]) for c in codes_u if c not in used_c and [v for v in cand[c] if v["id"] not in used_v]]
    no_vendor = [c for c in codes_u if c not in used_c and not [v for v in cand[c] if v["id"] not in used_v]]
    no_code = [v for v in vs if v["id"] not in used_v]
    by_elim = sorted(c for vid, (c, n) in done.items() if len(cand[c]) != 1)   # Kuerzel mit mehreren Erstkandidaten, erst durch Ausschluss eindeutig
    return {"ausschluss": by_elim, "zugeordnet": done, "mehrdeutig": ambiguous, "ohne_kuerzel": no_code, "ohne_vendor": no_vendor, "doppelt": duplicates(codes)}


def signal_for_text(text, codes):
    """Schwaches Zusatzsignal: Kuerzel, die im Text als eigenes Token (oder als Bestandteil von PO26-036-ALP) stehen. NIE allein zur Order-Zuordnung verwenden."""
    t = str(text or "")
    hits = []
    for c in codes:
        if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(c), t) and c not in hits:
            hits.append(c)
    return hits


def vendor_hint(text, vendors, id_map):
    """{vendor_id: [code]} fuer Lieferanten, deren Kuerzel im Text steht (id_map: {vendor_id: code}). Nur als Tipp fuer die Lieferantenwahl, nie fuer die Order."""
    codes = signal_for_text(text, list(id_map.values()))
    return {vid: c for vid, c in id_map.items() if c in codes}


def load_id_map(path=None):
    """{vendor_id: Kuerzel} aus output/phase2/B19/lieferanten_ids.json (vom Skript geschrieben); leer, wenn die Datei fehlt."""
    p = Path(path) if path else OUTDIR / "lieferanten_ids.json"
    try:
        return {vid: x["code"] for vid, x in json.load(open(p)).get("zugeordnet", {}).items()}
    except Exception:
        return {}


WARN_PREFIX = "Lieferant ohne Lieferanten-ID: "


def warnings_no_id(vendors, id_map):
    """Hinweise fuer den Tagesbericht, je Lieferant eine Zeile (kein automatisches Vergeben); leer, wenn keine Karte vorhanden oder alle ein Kuerzel haben."""
    if not id_map:
        return []
    return ["%s%s: Kuerzel im Stammdaten-Register vergeben und zuordnen lassen (wird nicht automatisch vergeben)" % (WARN_PREFIX, n) for n in new_vendors_without_id(vendors, id_map)]


def new_vendors_without_id(vendors, id_map):
    """Namen realer Lieferanten ohne Kuerzel (fuer den Tagesbericht-Hinweis; es wird nichts automatisch vergeben)."""
    return sorted(v["name"] for v in vendors if not SKIP_NAME.match(v.get("name") or "") and v["id"] not in id_map)


# ---------------- Browser (GraphQL) ----------------
_HEAD = r'''
const N=v=>({kind:'Name',value:v}); const V=n=>({kind:'Variable',name:N(n)}); const c=window.__APOLLO_CLIENT__;
const parseSel=s=>{const t=s.match(/[{}]|\w+/g);let i=0;const rec=()=>{const out=[];while(i<t.length&&t[i]!=='}'){const n=t[i++];const f={kind:'Field',name:N(n),arguments:[]};if(t[i]==='{'){i++;f.selectionSet={kind:'SelectionSet',selections:rec()};i++;}out.push(f);}return out;};return rec();};
const clean=a=>a===undefined||a===null?a:JSON.parse(JSON.stringify(a,(k,v)=>(k==='__typename'?undefined:v)));
const NN=(t)=>({kind:'NonNullType',type:{kind:'NamedType',name:N(t)}});
const mk=(op,name,vars,field,args,sel)=>({kind:'Document',definitions:[{kind:'OperationDefinition',operation:op,name:N(name),variableDefinitions:vars.map(([n,t,nn])=>({kind:'VariableDefinition',variable:V(n),type:nn?NN(t):{kind:'NamedType',name:N(t)}})),selectionSet:{kind:'SelectionSet',selections:[{kind:'Field',name:N(field),arguments:args.map(([a,v])=>({kind:'Argument',name:N(a),value:V(v)})),selectionSet:{kind:'SelectionSet',selections:parseSel(sel)}}]}}]});
const FIELDS=mk('query','Q',[['type','String'],['brandId','ID',1]],'materialCustomFields',[['type','type'],['brandId','brandId']],'id fieldName fieldType dbKey enumValues');
const BYID=mk('query','M',[['manufacturerId','String']],'manufacturerById',[['manufacturerId','manufacturerId']],'id name updatedAt customFields');
const UPD=mk('mutation','U',[['manufacturerId','String',1],['data','ManufacturerInput',1]],'updateManufacturer',[['manufacturerId','manufacturerId'],['manufacturerInput','data']],'id name updatedAt customFields');
const getFields=async()=>{const r=await c.query({query:FIELDS,variables:{type:__TYPE__,brandId:__BRAND__},fetchPolicy:'no-cache',errorPolicy:'all'});return clean((r.data&&r.data.materialCustomFields)||[]);};
const getV=async id=>{const r=await c.query({query:BYID,variables:{manufacturerId:id},fetchPolicy:'no-cache',errorPolicy:'all'});return r.data&&clean(r.data.manufacturerById);};
'''


def _js(body):
    return ("(async()=>{" + _HEAD + body + "})()").replace("__TYPE__", json.dumps(FIELD_TYPE)).replace("__BRAND__", json.dumps(BRAND_ID))


JS_FIELDS = _js("return await getFields();")
JS_READ = _js("const out={};const f=(await getFields()).find(x=>x.fieldName===__NAME__);out.field=f||null;out.v={};"
              "if(f){for(const id of __IDS__){try{const m=await getV(id);out.v[id]={v:((m&&m.customFields)||{})[f.dbKey]||null,cf:(m&&m.customFields)||{}};}catch(e){out.v[id]={err:String(e.message).slice(0,150)};}}}return out;")
# jobs: [{id, value}]: customFields (bestehende bleiben) + Feld; ManufacturerInput nur mit customFields (Rest unveraendert), danach zurueckgelesen und alles andere verglichen.
JS_SET = _js("const f=(await getFields()).find(x=>x.fieldName===__NAME__); if(!f) return {err:'Feld nicht gefunden'}; const out=[];"
             "const strip=m=>{const x=clean(m);delete x.customFields;delete x.updatedAt;return JSON.stringify(x);};"
             "const FULL=mk('query','F',[['manufacturerId','String']],'manufacturerById',[['manufacturerId','manufacturerId']],'id name updatedAt factorySize website description specializations certifications currency minimumOrderQuantity minimumColorQuantity customFields manufacturerCategory { id name } countryOfOrigin { id } addresses { id name main line1 line2 city zipCode country { id } } contacts { id name jobTitle phone email main chatMethod }');"
             "const full=async id=>{const r=await c.query({query:FULL,variables:{manufacturerId:id},fetchPolicy:'no-cache',errorPolicy:'all'});return r.data&&clean(r.data.manufacturerById);};"
             "for(const j of __JOBS__){try{const m=await full(j.id);if(!m){out.push({id:j.id,err:'nicht gefunden'});continue;}"
             "const cf=Object.assign({},m.customFields||{});if(cf[f.dbKey]&&String(cf[f.dbKey]).trim()){out.push({id:j.id,skip:'hat Wert',v:cf[f.dbKey]});continue;}"
             "cf[f.dbKey]=j.value;const before=strip(m);"
             "const r=await c.mutate({mutation:UPD,variables:{manufacturerId:j.id,data:{customFields:cf,expectedUpdatedAt:m.updatedAt}},errorPolicy:'all'});const err=(r.errors||[]).map(e=>e.message.slice(0,200));"
             "const a=await full(j.id);out.push({id:j.id,err:err.length?err:null,v:a&&(a.customFields||{})[f.dbKey],same:a?strip(a)===before:null,before:before,cfBefore:m.customFields||{}});}catch(e){out.push({id:j.id,err:String(e.message).slice(0,200)});}}"
             "return out;")
# Feld anlegen (nur wenn es noch nicht existiert). Eingabeform wie die App fuer Order-Felder: createMaterialCustomField(input{type,fieldName,fieldType,brandId})
JS_CREATE = _js("const ex=(await getFields()).find(x=>x.fieldName===__NAME__); if(ex) return {exists:ex};"
                "const CR=mk('mutation','C',[['input','MaterialCustomFieldInput',1]],'createMaterialCustomField',[['input','input']],'id fieldName fieldType dbKey');"
                "try{const r=await c.mutate({mutation:CR,variables:{input:{type:__TYPE__,fieldName:__NAME__,fieldType:'INPUT',brand:__BRAND__}},errorPolicy:'all'});"
                "return {created:clean(r.data&&r.data.createMaterialCustomField),err:(r.errors||[]).map(e=>e.message.slice(0,300))};}"
                "catch(e){const ne=e.networkError&&e.networkError.result&&e.networkError.result.errors;return {err:(ne||[{message:String(e.message)}]).map(x=>String(x.message).slice(0,300))};}")


def _fill(js, **kw):
    for k, v in kw.items():
        js = js.replace("__%s__" % k, json.dumps(v))
    return js


def run_js(js):
    from plm_intake.po_ids import run_js as _run
    return _run(js)


def read_values(ids, runner=run_js):
    return runner(_fill(JS_READ, NAME=FIELD_NAME, IDS=list(ids)))


def set_values(jobs, runner=run_js):
    return runner(_fill(JS_SET, NAME=FIELD_NAME, JOBS=jobs)) if jobs else []


def create_field(runner=run_js):
    return runner(_fill(JS_CREATE, NAME=FIELD_NAME))


def fetch_vendors(call=None):
    if call is None:
        import plm_client
        call = plm_client.call
    from plm_intake.context import fetch_all
    return fetch_all(call, "vendors")


def report(res, written=None, readback=None):
    done = res["zugeordnet"]
    L = ["# Lieferanten-IDs (Smilodox Lieferanten-ID)", "",
         "Quelle: Stammdaten-Register_Smilodox.xlsx (Google Drive), Blatt 'Lists', Spalte 'Supplier ID': %d Kuerzel. Das Register nennt keine Lieferantennamen; die Zuordnung ist aus dem Kuerzel abgeleitet (Namensbestandteile, nur eindeutige Treffer)." % len(set(c for c, _ in done.values()) | set(m[0] for m in res["mehrdeutig"]) | set(res["ohne_vendor"])), "",
         "Eindeutig zugeordnet: %d, mehrdeutig: %d, Kuerzel ohne PLM-Lieferant: %d, Lieferanten ohne Kuerzel: %d, doppelte Kuerzel im Register: %d." % (len(done), len(res["mehrdeutig"]), len(res["ohne_vendor"]), len(res["ohne_kuerzel"]), len(res["doppelt"])), "",
         "## Eindeutig", "", "| Kuerzel | PLM-Lieferant |" + (" im PLM |" if readback is not None else ""), "|---|---|" + ("---|" if readback is not None else "")]
    for vid, (c, n) in sorted(done.items(), key=lambda x: x[1][0]):
        L.append("| %s | %s |%s" % (c, n, (" %s |" % (readback.get(vid) or "-")) if readback is not None else ""))
    L += ["", "Davon erst durch Ausschluss eindeutig (mehrere Erstkandidaten, der andere Kandidat hat ein eigenes Kuerzel): %s." % (", ".join(res.get("ausschluss") or []) or "keine")]
    L += ["", "## Mehrdeutig (Mensch entscheidet, nichts geschrieben)", ""] + (["- %s: %s" % (c, "; ".join(ns)) for c, ns in res["mehrdeutig"]] or ["- keine"])
    L += ["", "## Kuerzel im Register ohne passenden PLM-Lieferanten", ""] + (["- %s" % c for c in res["ohne_vendor"]] or ["- keine"])
    L += ["", "## PLM-Lieferanten ohne Kuerzel", ""] + (["- %s" % v["name"] for v in res["ohne_kuerzel"]] or ["- keine"])
    L += ["", "## Doppelte Kuerzel im Register", ""] + (["- %s" % c for c in res["doppelt"]] or ["- keine"])
    return "\n".join(L) + "\n"


def plan(res, current):
    """current: {vendor_id: {v:..}} -> (zu_schreiben [(vid, code)], ok, abweichend [(vid, soll, ist)])."""
    todo, ok, wrong = [], 0, []
    for vid, (c, n) in res["zugeordnet"].items():
        cur = (current.get(vid) or {}).get("v")
        if not cur:
            todo.append((vid, c))
        elif cur == c:
            ok += 1
        else:
            wrong.append((vid, c, cur))
    return todo, ok, wrong


def main(argv=None):
    import argparse
    import datetime as dt
    ap = argparse.ArgumentParser()
    ap.add_argument("--create-field", action="store_true", help="Feld im PLM anlegen (Schreibzugriff)")
    ap.add_argument("--apply", action="store_true", help="Werte schreiben (Schreibzugriff)")
    ap.add_argument("--vendors-json", help="Lieferantenliste aus Datei statt REST (Test)")
    a = ap.parse_args(argv)
    vendors = json.load(open(a.vendors_json)) if a.vendors_json else fetch_vendors()
    vendors = vendors if isinstance(vendors, list) else vendors.get("data", [])
    codes = load_codes()
    res = assign(codes, vendors)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if a.create_field:
        print(json.dumps(create_field(), ensure_ascii=False))
    readback = None
    if a.apply or a.create_field:
        cur = read_values(list(res["zugeordnet"]))
        if not cur.get("field"):
            print("Feld fehlt im PLM (erst --create-field)"); return 2
        json.dump({"dbKey": cur["field"]["dbKey"], "id": cur["field"]["id"]}, open(FIELD_KEY_FILE, "w"))
        todo, ok, wrong = plan(res, cur["v"])
        if a.apply and todo:
            bk = ROOT / "output" / "backup" / ("vendors_before_lieferanten_ids_%s.json" % dt.date.today().isoformat())
            out = set_values([{"id": v, "value": c} for v, c in todo])
            old = json.load(open(bk)) if bk.exists() else {}
            old.update({r["id"]: {"before": json.loads(r["before"]), "customFields": r.get("cfBefore")} for r in out if r.get("before") and r["id"] not in old})
            bk.parent.mkdir(parents=True, exist_ok=True); json.dump(old, open(bk, "w"), ensure_ascii=False)
            bad = [r for r in out if r.get("err") or r.get("skip") or r.get("same") is False or r.get("v") != dict(todo).get(r["id"])]
            print("geschrieben %d, Probleme %d" % (len(out) - len(bad), len(bad)))
            for r in bad:
                print("  PROBLEM", {k: r.get(k) for k in ("id", "err", "skip", "same", "v")})
        cur = read_values(list(res["zugeordnet"]))
        readback = {v: (cur["v"].get(v) or {}).get("v") for v in res["zugeordnet"]}
    (OUTDIR / "lieferanten_ids.md").write_text(report(res, readback=readback))
    (OUTDIR / "lieferanten_ids.json").write_text(json.dumps({
        "zugeordnet": {vid: {"code": c, "name": n} for vid, (c, n) in res["zugeordnet"].items()},
        "mehrdeutig": [{"code": c, "kandidaten": ns} for c, ns in res["mehrdeutig"]],
        "ohne_vendor": res["ohne_vendor"], "ohne_kuerzel": [v["name"] for v in res["ohne_kuerzel"]], "doppelt": res["doppelt"],
        "im_plm": readback}, ensure_ascii=False, indent=1))
    print("zugeordnet %d, mehrdeutig %d, Kuerzel ohne Lieferant %d, Lieferanten ohne Kuerzel %d" % (len(res["zugeordnet"]), len(res["mehrdeutig"]), len(res["ohne_vendor"]), len(res["ohne_kuerzel"])))
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
