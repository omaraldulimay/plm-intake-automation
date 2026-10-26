"""Klaerfaelle der Einpflege im PLM (Custom Table "Klärfälle Einpflege", Kategorie = Lieferant).

Nur echte, bestellbezogene Faelle: Ereignis-Typ Versand/Termin/Zahlung/Aenderung/Verzoegerung/Qualitaet, nicht zuordenbar
(keine passende PO oder mehrere moeglich), und der Lieferant ist erkannt ODER eine PO-/Stylenummer ist genannt.
Nicht aufgenommen: Muster/Allgemeines ohne Bestellung, Paket-/Zolldienste, Fremdes ohne Lieferant und Nummer (z. B. Abo-Rechnungen).
Je Fall eine Zeile mit Marker ev:<hash> (keine Doppelten). Wird ein Fall spaeter einer PO zugeordnet, setzt der Lauf ihn auf "erledigt".
Schreibt nie in Bestellungen. Geloeste Faelle (spaeter einer PO zugeordnet) und Altlasten mit Status erledigt werden NACH Sicherung in intake/klaerfaelle_erledigt.json aus der Tabelle geloescht (deleteCustomRow), max. 50 je Lauf.

  python3 -m plm_intake.klaerfaelle --inbox <ordner>        Trockenlauf: zeigt, was eingetragen wuerde (ohne Browser)"""
import json
import re
from pathlib import Path

from plm_intake import core, events

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "output" / "intake" / "klaerfaelle.json"     # {"tableId": ..., "brandId": ...}
ART = {"SHIPMENT": "Versand", "SCHEDULE": "Termin", "PAYMENT": "Zahlung", "ORDER_CHANGE": "Änderung", "DELAY": "Verzögerung", "QUALITY": "Qualität"}
OHNE = "Ohne Lieferant"


def warum(reason):
    r = str(reason or "")
    if r.startswith("mehrdeutig:"):
        return "passt zu mehreren: " + r.split(":", 1)[1].strip()
    if "keine Order" in r:
        return "keine passende PO im PLM"
    return r


MAILS = Path.home() / "Library/CloudStorage/kontakt@firma.example/Meine Ablage/PLM-Mails"   # je Mail ein Ordner "<Datum>_<Zeit>_<Absender>_<Betreff>_<Gmail-ID>" mit mail.txt ("Message-ID: <id>")
NEU = ("Nummer", "Mögliche PO", "Aktion", "Zitat", "Absender", "Betreff", "Mail-ID", "Suche")


def mail_dirs(root=None):
    """Gmail-ID -> Fundort im Drive-Export: Sammeldatei mails_*.txt (aktuell) oder Ordnername (aeltere Mails). Leer, wenn nicht gemountet."""
    root = Path(root) if root else MAILS
    out = {}
    try:
        for d in root.iterdir():
            if d.is_dir() and "_" in d.name:
                out[d.name.rsplit("_", 1)[-1]] = "Ordner " + d.name
        for f in sorted(root.glob("mails_*.txt")):
            try:
                for i in re.findall(r"^Message-ID: (\w+)", f.read_text(errors="ignore"), re.M):
                    out[i] = "Datei " + f.name
            except OSError:
                pass
    except OSError:
        return {}
    return out


def scrub(text):
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    for pat in core.BANK_PATTERNS:
        t = re.sub(pat, "[Bankdaten entfernt]", t)
    return t


def suche(mail_id, frm, date, dirs=None):
    """Suchbegriff: Gmail-ID zuerst (Drive-Volltext trifft mail.txt, Zeile Message-ID), dann Export-Ordner und Gmail-Filter."""
    if not mail_id:
        return ""
    parts = [str(mail_id)]
    d = (dirs or {}).get(str(mail_id))
    if d:
        parts.append("PLM-Mails/" + d)
    a = re.search(r"[\w.+-]+@[\w.-]+", str(frm or ""))
    dm = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(date or ""))
    if a and dm:
        import datetime
        d0 = datetime.date(*map(int, dm.groups()))
        parts.append("Gmail: from:%s after:%s before:%s" % (a.group(0), (d0 - datetime.timedelta(days=1)).strftime("%Y/%m/%d"), (d0 + datetime.timedelta(days=2)).strftime("%Y/%m/%d")))
    return " | ".join(parts)[:400]


def select(unmatched, vendors, vendor_aliases=None, dom=None, dirs=None):
    """Nicht zugeordnete Ereignisse -> Zeilen (dict mit marker, category, values). Rein, testbar."""
    rows, seen = [], set()
    for u in unmatched:
        e, reason = u["event"], str(u.get("reason") or "")
        if reason.startswith("info:") or e.get("type") not in ART:
            continue
        ref = e.get("ref") or {}
        v = events.vendor_of(e, vendors, vendor_aliases, dom)
        nums = events.codes(ref.get("po_number"), ref.get("style"))
        if not v and not nums:
            continue
        mk = events.marker(e)
        if mk in seen:
            continue
        seen.add(mk)
        m = e.get("_mail") or {}
        datum = str(e.get("date") or m.get("date") or "")[:10]
        ident = " / ".join(x for x in (ref.get("po_number"), ref.get("style"), ref.get("container")) if x)
        was = str(e.get("summary") or "").strip()
        if ident and core.norm(ident) not in core.norm(was):
            was = "%s (%s)" % (was, ident)
        rows.append({"marker": mk, "category": v["name"] if v else OHNE,
                     "values": {"Datum": datum if re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum) else None, "Art": ART[e["type"]], "Was": was[:300],
                                "Warum offen": warum(reason)[:200],
                                "Nummer": ident[:200],
                                "Mögliche PO": reason.split(":", 1)[1].strip()[:300] if reason.startswith("mehrdeutig:") and "laufende Orders" not in reason else "",
                                "Aktion": scrub(e.get("action_needed"))[:300],
                                "Zitat": scrub(e.get("source_quote"))[:300],
                                "Absender": scrub(m.get("from"))[:200],
                                "Betreff": scrub(m.get("subject"))[:300],
                                "Mail-ID": str(m.get("id") or ""),
                                "Suche": suche(m.get("id"), m.get("from"), m.get("date"), dirs),
                                "Quelle": ("Mail %s | %s | ev:%s" % (str(m.get("date") or "")[:16], str(m.get("subject") or "")[:70], mk)),
                                "Status": "offen"}})
    return rows


SYNC_JS = r'''(async () => {
  const P = __PAYLOAD__;
  const c = window.__APOLLO_CLIENT__; const N = v => ({ kind: 'Name', value: v });
  const F = (n, s) => ({ kind: 'Field', name: N(n), selectionSet: s ? { kind: 'SelectionSet', selections: s } : undefined });
  const V = (n, t) => ({ kind: 'VariableDefinition', variable: { kind: 'Variable', name: N(n) }, type: { kind: 'NonNullType', type: { kind: 'NamedType', name: N(t) } } });
  const A = n => ({ kind: 'Argument', name: N(n), value: { kind: 'Variable', name: N(n) } });
  const op = (kind, name, vars, sel) => ({ kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: kind, variableDefinitions: vars.map(x => V(x[0], x[1])), selectionSet: { kind: 'SelectionSet', selections: [{ kind: 'Field', name: N(name), arguments: vars.map(x => A(x[0])), selectionSet: { kind: 'SelectionSet', selections: sel } }] } }] });
  const out = { created: 0, categories: 0, errors: [] };
  const tq = await c.query({ query: op('query', 'customTable', [['id', 'ID']], [F('id'), F('categories', [F('id'), F('name')])]), variables: { id: P.tableId }, fetchPolicy: 'no-cache', errorPolicy: 'all' });
  const cats = {}; ((tq.data && tq.data.customTable && tq.data.customTable.categories) || []).forEach(x => { cats[x.name] = x.id; });
  const rq = await c.query({ query: op('query', 'customRowsByTable', [['tableId', 'ID']], [F('id'), F('categoryId'), F('values'), F('createdAt')]), variables: { tableId: P.tableId }, fetchPolicy: 'no-cache', errorPolicy: 'all' });
  const rows = (rq.data && rq.data.customRowsByTable) || [];
  const mk = r => { const m = /ev:([0-9a-f]{8})/.exec(String((r.values || {}).Quelle || '')); return m ? m[1] : null; };
  const have = new Set(rows.map(mk).filter(Boolean));
  for (const r of P.rows) {
    if (have.has(r.marker)) continue;
    try {
      if (!cats[r.category]) {
        const cr = await c.mutate({ mutation: op('mutation', 'createCustomTableCategory', [['input', 'CreateCustomTableCategoryInput']], [F('id'), F('name')]), variables: { input: { tableId: P.tableId, brandId: P.brandId, name: r.category } }, errorPolicy: 'all' });
        if (!cr.data || !cr.data.createCustomTableCategory) { out.errors.push('Kategorie ' + r.category + ': ' + (cr.errors || []).map(e => e.message).join('; ').slice(0, 160)); continue; }
        cats[r.category] = cr.data.createCustomTableCategory.id; out.categories++;
      }
      const vals = {}; Object.entries(r.values).forEach(([k, v]) => { if (v !== null && v !== '') vals[k] = v; });
      const rr = await c.mutate({ mutation: op('mutation', 'createCustomRow', [['input', 'CreateCustomRowInput']], [F('id')]), variables: { input: { tableId: P.tableId, brandId: P.brandId, categoryId: cats[r.category], values: vals } }, errorPolicy: 'all' });
      if (rr.data && rr.data.createCustomRow) { out.created++; have.add(r.marker); } else out.errors.push('Zeile ' + r.marker + ': ' + (rr.errors || []).map(e => e.message).join('; ').slice(0, 160));
    } catch (e) { out.errors.push(String(e.message).slice(0, 160)); }
  }
  out.filled = 0;
  const want = {}; P.rows.forEach(r => { want[r.marker] = r.values; });
  for (const r of rows) {
    const m = mk(r), w = m && want[m];
    if (!w) continue;
    const cur = r.values || {}; const add = {};
    for (const k of P.fill) { const v = w[k]; if ((cur[k] === undefined || cur[k] === null || cur[k] === '') && v !== undefined && v !== null && v !== '') add[k] = v; }
    if (!Object.keys(add).length) continue;
    try {
      const ur = await c.mutate({ mutation: op('mutation', 'updateCustomRow', [['id', 'ID'], ['input', 'UpdateCustomRowInput']], [F('id')]), variables: { id: r.id, input: { values: { ...cur, ...add } } }, errorPolicy: 'all' });
      if (ur.data && ur.data.updateCustomRow) { out.filled++; r.values = { ...cur, ...add }; } else out.errors.push('Nachfuellen ' + m + ': ' + (ur.errors || []).map(e => e.message).join('; ').slice(0, 160));
    } catch (e) { out.errors.push(String(e.message).slice(0, 160)); }
  }
  // Loesch-Kandidaten (geloest laut Plan oder Status erledigt, nur mit Marker); geloescht wird erst nach Sicherung in einem zweiten Schritt (DELETE_JS)
  const resolved = new Set(P.resolved); const catName = {}; Object.entries(cats).forEach(([n, id]) => { catName[id] = n; });
  out.cands = rows.filter(r => { const m = mk(r); return m && (resolved.has(m) || (r.values || {}).Status === 'erledigt'); })
    .map(r => ({ id: r.id, marker: mk(r), category: catName[r.categoryId] || null, createdAt: r.createdAt, values: r.values || {} }));
  const after = await c.query({ query: op('query', 'customRowsByTable', [['tableId', 'ID']], [F('id'), F('values')]), variables: { tableId: P.tableId }, fetchPolicy: 'no-cache', errorPolicy: 'all' });
  out.rows_total = ((after.data && after.data.customRowsByTable) || []).length;
  out.open_total = ((after.data && after.data.customRowsByTable) || []).filter(r => (r.values || {}).Status === 'offen').length;
  return out;
})()'''

DELETE_JS = r'''(async () => {
  const P = __PAYLOAD__;
  const c = window.__APOLLO_CLIENT__; const N = v => ({ kind: 'Name', value: v });
  const F = (n, s) => ({ kind: 'Field', name: N(n), selectionSet: s ? { kind: 'SelectionSet', selections: s } : undefined });
  const V = (n, t) => ({ kind: 'VariableDefinition', variable: { kind: 'Variable', name: N(n) }, type: { kind: 'NonNullType', type: { kind: 'NamedType', name: N(t) } } });
  const rowsDoc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'query', variableDefinitions: [V('tableId', 'ID')], selectionSet: { kind: 'SelectionSet', selections: [{ kind: 'Field', name: N('customRowsByTable'), arguments: [{ kind: 'Argument', name: N('tableId'), value: { kind: 'Variable', name: N('tableId') } }], selectionSet: { kind: 'SelectionSet', selections: [F('id'), F('values')] } }] } }] };
  const delDoc = { kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: 'mutation', variableDefinitions: [V('id', 'ID')], selectionSet: { kind: 'SelectionSet', selections: [{ kind: 'Field', name: N('deleteCustomRow'), arguments: [{ kind: 'Argument', name: N('id'), value: { kind: 'Variable', name: N('id') } }] }] } }] };
  const read = async () => { const q = await c.query({ query: rowsDoc, variables: { tableId: P.tableId }, fetchPolicy: 'no-cache', errorPolicy: 'all' }); return (q.data && q.data.customRowsByTable) || []; };
  const mk = r => { const m = /ev:([0-9a-f]{8})/.exec(String((r.values || {}).Quelle || '')); return m ? m[1] : null; };
  const out = { deleted: 0, errors: [] };
  const resolved = new Set(P.resolved); const rows = await read(); const byId = {}; rows.forEach(r => { byId[r.id] = r; });
  const gone = [];
  for (const it of P.items) {
    const r = byId[it.id];
    if (!r || mk(r) !== it.marker || !(resolved.has(it.marker) || (r.values || {}).Status === 'erledigt')) { out.errors.push('uebersprungen ' + it.marker); continue; }
    try {
      const dr = await c.mutate({ mutation: delDoc, variables: { id: it.id }, errorPolicy: 'all' });
      if (dr.errors && dr.errors.length) out.errors.push('Loeschen ' + it.marker + ': ' + dr.errors.map(e => e.message).join('; ').slice(0, 160)); else gone.push(it.id);
    } catch (e) { out.errors.push(String(e.message).slice(0, 160)); }
  }
  const after = await read(); const left = new Set(after.map(r => r.id));
  out.deleted = gone.filter(id => !left.has(id)).length;
  if (out.deleted !== gone.length) out.errors.push('Zuruecklesen: ' + (gone.length - out.deleted) + ' Zeile(n) noch da');
  out.rows_total = after.length; out.open_total = after.filter(r => (r.values || {}).Status === 'offen').length;
  return out;
})()'''

MAX_DELETE = 50
BACKUP = ROOT / "output" / "intake" / "klaerfaelle_erledigt.json"


def backup_entries(cands, order_of, lauf, now=None):
    """Sicherungseintraege je Loesch-Kandidat (alle Felder der Zeile bleiben in 'felder' erhalten)."""
    import datetime
    ts = (now or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M")
    out = []
    for c in cands:
        v = c.get("values") or {}
        out.append({"Marker": c["marker"], "Datum": v.get("Datum"), "Art": v.get("Art"), "Text": v.get("Was"), "Order": order_of.get(c["marker"]),
                    "geloest am": ts, "Lauf": lauf, "Kategorie": c.get("category"), "felder": v, "id": c.get("id")})
    return out


def save_backup(entries, path=None):
    """Haengt Eintraege an (ohne Doppelte je Marker+id), schreibt atomar und liest zur Kontrolle zurueck. True nur, wenn alle drin sind."""
    path = Path(path) if path else BACKUP
    old = json.loads(path.read_text()) if path.exists() else []
    have = {(e.get("Marker"), e.get("id")) for e in old}
    new = old + [e for e in entries if (e["Marker"], e.get("id")) not in have]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp"); tmp.write_text(json.dumps(new, ensure_ascii=False, indent=1)); tmp.replace(path)
    back = {(e.get("Marker"), e.get("id")) for e in json.loads(path.read_text())}
    return all((e["Marker"], e.get("id")) in back for e in entries)


def delete_solved(cands, resolved, cfg, runner, order_of=None, lauf="", backup_path=None, dry=False):
    """Kandidaten sichern, dann loeschen (max. MAX_DELETE). Rest bleibt fuer den naechsten Lauf. Trockenlauf: nur zaehlen."""
    cands = [c for c in cands if c.get("marker") and c.get("id")]
    todo = cands[:MAX_DELETE]
    res = {"deleted": 0, "pending": len(cands) - len(todo), "errors": []}
    if dry or not todo:
        res["would_delete"] = len(todo)
        return res
    if not save_backup(backup_entries(todo, order_of or {}, lauf), backup_path):
        res["errors"].append("Sicherung nicht geschrieben, nichts geloescht")
        return res
    js = DELETE_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"], "resolved": sorted(resolved), "items": [{"id": c["id"], "marker": c["marker"]} for c in todo]}, ensure_ascii=False))
    r = runner(js) or {}
    res.update({k: r.get(k) for k in ("deleted", "rows_total", "open_total")})
    res["errors"] += r.get("errors") or []
    return res


def sync(pl, ctx, vendor_aliases=None, runner=None, lauf=""):
    """Neue Klaerfaelle eintragen, zugeordnete abhaken. pl = events.plan(...); runner(js) -> Ergebnis (Browser)."""
    cfg = json.loads(CFG.read_text())
    dom = events.domain_vendors(ctx["vendors"])
    rows = select(pl["unmatched"], ctx["vendors"], vendor_aliases, dom, mail_dirs())
    resolved = sorted({l["marker"] for o in pl["orders"] for l in o["lines"]})
    js = SYNC_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"], "brandId": cfg["brandId"], "rows": rows, "resolved": resolved, "fill": list(NEU)}, ensure_ascii=False))
    if runner is None:
        from plm_intake.barcodes import run_js as runner
    res = runner(js) or {}
    cands = res.pop("cands", [])
    order_of = {l["marker"]: o.get("title") for o in pl["orders"] for l in o["lines"]}
    d = delete_solved(cands, set(resolved), cfg, runner, order_of, lauf or "auto_run")
    res["geloescht"] = d.get("deleted", 0); res["loeschen_offen"] = d.get("pending", 0)
    res["errors"] = (res.get("errors") or []) + d["errors"]
    for k in ("rows_total", "open_total"):
        if d.get(k) is not None:
            res[k] = d[k]
    return rows, res


def cleanup_erledigt(runner=None, dry=True, lauf="aufraeumen", full_backup=None):
    """Einmal-Aufraeumen: alle Zeilen mit Status erledigt sichern und loeschen (ohne neue Zeilen anzulegen)."""
    cfg = json.loads(CFG.read_text())
    js = SYNC_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"], "brandId": cfg["brandId"], "rows": [], "resolved": [], "fill": []}))
    if runner is None:
        from plm_intake.barcodes import run_js as runner
    res = runner(js) or {}
    cands = res.get("cands", [])
    if not dry and cands and full_backup:   # Vollsicherung (alle Felder) VOR dem Loeschen
        Path(full_backup).parent.mkdir(parents=True, exist_ok=True); Path(full_backup).write_text(json.dumps(cands, ensure_ascii=False, indent=1))
    return cands, delete_solved(cands, set(), cfg, runner, {}, lauf, dry=dry)


def main(argv=None):
    import argparse
    import os
    from plm_intake import ledger
    from plm_intake.context import load_context, add_po_numbers
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=os.path.expanduser("~/Library/CloudStorage/kontakt@firma.example/Meine Ablage/Inbox"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--aufraeumen", action="store_true", help="alle Zeilen mit Status erledigt sichern und loeschen (Trockenlauf ohne --apply)")
    a = ap.parse_args(argv)
    if a.aufraeumen:
        import datetime
        bk = ROOT / "output" / "backup" / ("klaerfaelle_erledigt_%s.json" % datetime.date.today().isoformat())
        cands, res = cleanup_erledigt(dry=not a.apply, full_backup=bk)
        print("Kandidaten:", len(cands), "| Backup:", bk if a.apply else "(erst mit --apply)")
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    intake = ROOT / "output" / "intake"
    led = ledger.load(intake / "ledger.json")
    evs = [f for f in sorted(Path(a.inbox).glob("*_events.json")) if not ledger.is_done(led, f)]
    ctx = load_context(); add_po_numbers(ctx)
    al = json.load(open(intake / "vendor_aliases.json")) if (intake / "vendor_aliases.json").exists() else {}
    poal = json.load(open(intake / "po_aliases.json")) if (intake / "po_aliases.json").exists() else {}
    pl = events.plan(events.load_events(evs), ctx["orders"], ctx["vendors"], poal, al, vendor_only=True, products=ctx["products"], style_aliases=ctx.get("style_aliases"), event_overrides=events.load_event_overrides(intake))
    if a.apply:
        rows, res = sync(pl, ctx, al)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        rows = select(pl["unmatched"], ctx["vendors"], al, events.domain_vendors(ctx["vendors"]))
        from collections import Counter
        print("Klaerfaelle (Trockenlauf): %d" % len(rows))
        for k, n in Counter(r["category"] for r in rows).most_common():
            print("  %3d  %s" % (n, k))


if __name__ == "__main__":
    main()
