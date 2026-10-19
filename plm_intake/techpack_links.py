"""Batch 10 Teil A: Techpack-/Spec-Dateien aus dem Mail-Export als Drive-Links an die Produkte hängen (addProductAttachment). Nur Links, nichts wird versendet oder geteilt.

  python3 -m plm_intake.techpack_links            TROCKENLAUF: output/phase2/B10/techpack_links_plan.md (+ .json)
  python3 -m plm_intake.techpack_links --apply    schreibt die Anhänge (nur neue), liest je Produkt zurück

Quellen: output/phase2/*/sources.json (Typ TP / Spec), Datei lokal in Drive Desktop (PLM-Mails/Anhaenge), Drive-ID aus dem Dateiattribut com.google.drivefs.item-id.
Zuordnung nur EXAKT: Stylecode im Dateinamen (normalisiert) = SKU eines PLM-Produkts. Mehrdeutig/ohne Treffer -> Liste "nicht zugeordnet" (kein Raten).
Je Produkt und Typ (TP, Spec) nur die NEUESTE Fassung; schon vorhandene Anhänge (gleiche Drive-ID oder gleicher Name) werden übersprungen. Nie löschen."""
import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output" / "phase2" / "B10"
ANH = Path.home() / "Library/CloudStorage/kontakt@firma.example/Meine Ablage/PLM-Mails/Anhaenge"
TOKEN_RX = re.compile(r"(?:[A-Za-z]{1,6}[-_ ]){0,2}[A-Za-z]{1,6}[-_ ]?\d{2,6}(?:[-_]\d{1,3})?[A-Za-z]?|\d{2}[A-Za-z]\d{2}[-_ ]?\d{3}|\d{5,7}")
MIME = {".pdf": "application/pdf", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xls": "application/vnd.ms-excel",
        ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_NEW = int(os.environ.get("PLM_MAX_ATT", "300"))


def nk(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def drive_id(path):
    r = subprocess.run(["xattr", "-p", "com.google.drivefs.item-id#S", str(path)], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def load_sources():
    seen, out = {}, []
    for f in sorted(glob.glob(str(ROOT / "output/phase2/*/sources.json"))):
        d = json.load(open(f))
        for s in (d if isinstance(d, list) else d.get("sources", [])):
            if s.get("typ") in ("TP", "Spec") and s.get("datei") and s["datei"] not in seen:
                seen[s["datei"]] = 1
                out.append(s)
    return out


def display_name(datei):
    return re.sub(r"^\d{4}-\d{2}-\d{2}_[0-9a-f]{16}_", "", datei)


def targets_of(name, by_key):
    toks = {nk(t) for t in TOKEN_RX.findall(re.sub(r"\.[A-Za-z]{2,4}$", "", name))}
    hits = []
    for t in toks:
        if len(t) < 4:
            continue
        if t in by_key:
            hits += by_key[t]
        else:   # Varianten-Suffix am PLM-Produkt (XW-042-CROC / -CHET, 561871_A): nur Buchstaben-Suffix, hoechstens 3 Produkte
            ext = [p for k, L in by_key.items() if k.startswith(t) and re.fullmatch(r"[a-z]{1,6}", k[len(t):]) for p in L]
            if 0 < len(ext) <= 3:
                hits += ext
    uniq = {p["id"]: p for p in hits}
    return list(uniq.values())


def plan(products):
    by_key = collections.defaultdict(list)
    for p in products:
        if p.get("sku") and not re.match(r"(?i)zz|t1-", str(p["sku"])):
            by_key[nk(p["sku"])].append(p)
    items, unassigned = [], []
    for s in load_sources():
        name = display_name(s["datei"])
        tg = targets_of(name, by_key)
        if not tg:
            unassigned.append((s["typ"], name, "kein exakter Stylecode im Dateinamen"))
            continue
        if len(tg) > 3 and not all(nk(t["sku"]) == nk(tg[0]["sku"]) for t in tg):
            unassigned.append((s["typ"], name, "mehr als 3 Produkte: %s" % ", ".join(t["sku"] for t in tg[:5])))
            continue
        for p in tg:
            items.append({"productId": p["id"], "sku": p["sku"], "typ": s["typ"], "name": name, "datei": s["datei"], "datum": s.get("datum") or "", "mail_id": s.get("mail_id")})
    # nur neueste Fassung je Produkt + Typ
    best = {}
    for it in items:
        k = (it["productId"], it["typ"])
        if k not in best or (it["datum"], it["datei"]) > (best[k]["datum"], best[k]["datei"]):
            best[k] = it
    return list(best.values()), unassigned


JS = r'''(async () => {
  const N = v => ({ kind: 'Name', value: v }); const V = n => ({ kind: 'Variable', name: N(n) });
  const F = (name, args, sel) => ({ kind: 'Field', name: N(name), arguments: args || [], selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined });
  const A = (n, v) => ({ kind: 'Argument', name: N(n), value: v });
  const T = (n, nn) => nn ? { kind: 'NonNullType', type: { kind: 'NamedType', name: N(n) } } : { kind: 'NamedType', name: N(n) };
  const VD = l => l.map(x => ({ kind: 'VariableDefinition', variable: V(x[0]), type: x[1] }));
  const c = window.__APOLLO_CLIENT__; const MODE = '__MODE__', JOBS = __JOBS__; const out = { existing: {}, added: [], err: [] };
  const qA = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', variableDefinitions: VD([['productId', T('String', 1)]]),
    selectionSet: { kind: 'SelectionSet', selections: [F('productAttachments', [A('productId', V('productId'))], [F('id'), F('name'), F('fileUrl')])] } }] };
  const mA = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', variableDefinitions: VD([['productId', T('String', 1)], ['input', T('AddProductAttachmentInput', 1)]]),
    selectionSet: { kind: 'SelectionSet', selections: [F('addProductAttachment', [A('productId', V('productId')), A('input', V('input'))], [F('id'), F('name'), F('fileUrl')])] } }] };
  const read = async pid => { try { const r = await c.query({ query: qA, variables: { productId: pid }, fetchPolicy: 'no-cache', errorPolicy: 'all' }); return (r.data && r.data.productAttachments) || []; } catch (e) { return null; } };
  const pids = [...new Set(JOBS.map(j => j.productId))];
  for (const pid of pids) out.existing[pid] = await read(pid);
  if (MODE === 'apply') {
    for (const j of JOBS) {
      const ex = out.existing[j.productId] || [];
      if (ex.some(a => (a.fileUrl || '').includes(j.driveId) || (a.name || '').toLowerCase() === j.name.toLowerCase())) continue;
      try { const r = await c.mutate({ mutation: mA, variables: { productId: j.productId, input: { name: j.name, fileUrl: 'https://drive.google.com/file/d/' + j.driveId + '/view', fileType: j.mime } }, errorPolicy: 'all' });
            if (r.data && r.data.addProductAttachment) out.added.push({ productId: j.productId, name: j.name, id: r.data.addProductAttachment.id }); else out.err.push({ productId: j.productId, name: j.name, err: (r.errors || []).map(e => e.message.slice(0, 120)) }); }
      catch (e) { out.err.push({ productId: j.productId, name: j.name, err: String(e.message).slice(0, 120) }); }
    }
    out.after = {}; for (const pid of pids) out.after[pid] = await read(pid);
  }
  return out;
})()'''


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake import barcodes as bc
    from plm_intake.context import fetch_all
    OUT.mkdir(parents=True, exist_ok=True)
    products = fetch_all(plm_client.call, "products")
    items, unassigned = plan(products)
    jobs, nolocal = [], []
    for it in items:
        p = ANH / it["datei"]
        did = drive_id(p) if p.exists() else None
        if not did:
            nolocal.append(it); continue
        ext = os.path.splitext(it["name"])[1].lower()
        jobs.append({**it, "driveId": did, "mime": MIME.get(ext, "application/octet-stream")})
    res = bc.run_js(JS.replace("__MODE__", "apply" if False else "dry").replace("__JOBS__", json.dumps(jobs, ensure_ascii=False)))
    todo = []
    for j in jobs:
        ex = res["existing"].get(j["productId"])
        if ex is None:
            nolocal.append(j); continue
        if any(j["driveId"] in (x.get("fileUrl") or "") or (x.get("name") or "").lower() == j["name"].lower() for x in ex):
            continue
        todo.append(j)
    rep = ["# Techpack-/Spec-Links (%s)" % ("AUSGEFUEHRT" if a.apply else "TROCKENLAUF"), "", "Quellen TP/Spec: %d Dateien | Zuordnungen (neueste je Produkt+Typ): %d | schon vorhanden: %d | NEU: %d | nicht zuordenbar: %d | Lesefehler/ohne lokale Datei: %d" % (
        len(load_sources()), len(items), len(jobs) - len(todo), len(todo), len(unassigned), len(nolocal)), "", "## Neu anzuhängen", "", "| SKU | Typ | Datei |", "|---|---|---|"]
    rep += ["| %s | %s | %s |" % (j["sku"], j["typ"], j["name"][:70]) for j in todo]
    rep += ["", "## Nicht zugeordnet (Mensch/spätere Regel)", ""] + ["- %s | %s | %s" % u for u in unassigned[:200]]
    (OUT / "techpack_links_plan.json").write_text(json.dumps({"todo": todo, "unassigned": unassigned}, ensure_ascii=False, indent=1))
    if a.apply and todo:
        if len(todo) > MAX_NEW:
            print("ABBRUCH: %d neue Anhaenge > Limit %d (PLM_MAX_ATT)" % (len(todo), MAX_NEW)); return 2
        r2 = bc.run_js(JS.replace("__MODE__", "apply").replace("__JOBS__", json.dumps(todo, ensure_ascii=False)))
        bad = []
        for j in todo:
            after = (r2.get("after") or {}).get(j["productId"]) or []
            if not any(j["driveId"] in (x.get("fileUrl") or "") for x in after):
                bad.append("%s %s" % (j["sku"], j["name"]))
        rep += ["", "## Schreibergebnis", "- angehaengt: %d, Fehler: %d" % (len(r2.get("added") or []), len(r2.get("err") or []))]
        rep += ["- Fehler: %s" % json.dumps(r2.get("err"), ensure_ascii=False)[:600]] if r2.get("err") else []
        rep += ["", "## Rueckpruefung", "- %s" % ("ALLE %d Anhaenge im PLM zurueckgelesen" % len(todo) if not bad else "ABWEICHUNG: %s" % bad[:20])]
    (OUT / "techpack_links_plan.md").write_text("\n".join(rep))
    print("\n".join(rep[:12 + min(len(todo), 40)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
