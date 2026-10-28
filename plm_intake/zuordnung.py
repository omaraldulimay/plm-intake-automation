"""Zuordnung aus der PLM-Tabelle 'Klärfälle Einpflege': Spalte 'Zuordnung' (Mensch) -> event_overrides / po_aliases, Spalte 'Rückmeldung' (Skript).

Eingabe je Zeile: PO-ID (PO26-057) | #<Order-Nr> | Order-Titel | info (kein Bestellbezug). Gilt fuer ALLE offenen Zeilen derselben Mail-ID und (bei Order-Zuordnung) desselben Gmail-Verlaufs mit gleichem Lieferanten, ausser der Wert endet auf ' !nur'.
Ungueltig/Konflikt -> nichts zugeordnet, Hinweis in 'Rückmeldung', 'Zuordnung' bleibt stehen. Bestehende event_overrides werden nie ueberschrieben.
Die Zeile verschwindet ueber die bestehende Loeschlogik (klaerfaelle.delete_solved), sobald der Lauf das Ereignis der Order zugeordnet hat; info-Zeilen bekommen Status 'erledigt'.

  python3 -m plm_intake.zuordnung --spalten [--apply]      Spalten 'Zuordnung' und 'Rückmeldung' additiv anlegen (Trockenlauf zeigt nur den Stand)
  python3 -m plm_intake.zuordnung [--apply] [--nur-marker ev:xxxx]   Eingaben einlesen (Trockenlauf Standard)"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from plm_intake import alias_learn, core, events, klaerfaelle, po_ids  # noqa: E402

MAX_ROWS = 30
NEW_COLS = ("Zuordnung", "Rückmeldung")
NUR = re.compile(r"\s*!nur\s*$", re.I)

_HEAD = r'''const c = window.__APOLLO_CLIENT__; const N = v => ({ kind: 'Name', value: v });
  const F = (n, s) => ({ kind: 'Field', name: N(n), selectionSet: s ? { kind: 'SelectionSet', selections: s } : undefined });
  const V = (n, t) => ({ kind: 'VariableDefinition', variable: { kind: 'Variable', name: N(n) }, type: { kind: 'NonNullType', type: { kind: 'NamedType', name: N(t) } } });
  const A = n => ({ kind: 'Argument', name: N(n), value: { kind: 'Variable', name: N(n) } });
  const op = (kind, name, vars, sel) => ({ kind: 'Document', definitions: [{ kind: 'OperationDefinition', operation: kind, variableDefinitions: vars.map(x => V(x[0], x[1])), selectionSet: { kind: 'SelectionSet', selections: [{ kind: 'Field', name: N(name), arguments: vars.map(x => A(x[0])), selectionSet: sel ? { kind: 'SelectionSet', selections: sel } : undefined }] } }] });
  const readRows = async () => { const q = await c.query({ query: op('query', 'customRowsByTable', [['tableId', 'ID']], [F('id'), F('values')]), variables: { tableId: P.tableId }, fetchPolicy: 'no-cache', errorPolicy: 'all' }); return (q.data && q.data.customRowsByTable) || []; };
  const readFields = async () => { const q = await c.query({ query: op('query', 'customTable', [['id', 'ID']], [F('id'), F('fields', [F('key'), F('type'), F('required'), F('enumValues'), F('multipleSelection')])]), variables: { id: P.tableId }, fetchPolicy: 'no-cache', errorPolicy: 'all' }); return ((q.data && q.data.customTable && q.data.customTable.fields) || []).map(f => ({ key: f.key, type: f.type, required: f.required, enumValues: f.enumValues, multipleSelection: f.multipleSelection })); };'''

COLS_JS = '''(async () => {
  const P = __PAYLOAD__;
  ''' + _HEAD + r'''
  const before = await readFields(); const rowsBefore = await readRows();
  const out = { before: before.map(f => f.key), added: [], errors: [] };
  const add = P.cols.filter(k => !before.some(f => f.key === k));
  if (add.length && P.apply) {
    const fields = before.concat(add.map(k => ({ key: k, type: 'string', required: false, enumValues: null, multipleSelection: false })));
    const r = await c.mutate({ mutation: op('mutation', 'updateCustomTable', [['id', 'ID'], ['input', 'UpdateCustomTableInput']], [F('id')]), variables: { id: P.tableId, input: { fields } }, errorPolicy: 'all' });
    if (!r.data || !r.data.updateCustomTable) out.errors.push((r.errors || []).map(e => e.message).join('; ').slice(0, 200)); else out.added = add;
  } else out.would_add = add;
  const after = await readFields(); const rowsAfter = await readRows();
  out.after = after.map(f => f.key); out.rows_before = rowsBefore.length; out.rows_after = rowsAfter.length;
  out.fields_unchanged = before.every((f, i) => JSON.stringify(f) === JSON.stringify(after[i]));
  out.rows_unchanged = JSON.stringify(rowsBefore.map(r => [r.id, r.values])) === JSON.stringify(rowsAfter.map(r => [r.id, r.values]));
  return out;
})()'''

# Reihenfolge der Spalten: zuerst das, was der Mensch zum Zuordnen braucht, ganz hinten die Technik
REIHENFOLGE = ("Status", "Auswahl", "Zuordnung", "Datum", "Was", "Warum offen", "Mögliche PO", "Betreff", "Rückmeldung", "Details", "Mail-ID", "Quelle")

ORDER_JS = '''(async () => {
  const P = __PAYLOAD__;
  ''' + _HEAD + r'''
  const before = await readFields(); const rowsBefore = await readRows();
  const rank = k => { const i = P.order.indexOf(k); return i < 0 ? 999 : i; };
  const fields = before.slice().sort((a, b) => rank(a.key) - rank(b.key));
  const out = { before: before.map(f => f.key), after_plan: fields.map(f => f.key), errors: [] };
  if (P.apply) {
    const r = await c.mutate({ mutation: op('mutation', 'updateCustomTable', [['id', 'ID'], ['input', 'UpdateCustomTableInput']], [F('id')]), variables: { id: P.tableId, input: { fields } }, errorPolicy: 'all' });
    if (!r.data || !r.data.updateCustomTable) out.errors.push((r.errors || []).map(e => e.message).join('; ').slice(0, 200));
  }
  const after = await readFields(); const rowsAfter = await readRows();
  out.after = after.map(f => f.key); out.rows_unchanged = JSON.stringify(rowsBefore.map(r => [r.id, r.values])) === JSON.stringify(rowsAfter.map(r => [r.id, r.values]));
  out.fields_same_defs = JSON.stringify(before.slice().sort((a, b) => a.key.localeCompare(b.key))) === JSON.stringify(after.slice().sort((a, b) => a.key.localeCompare(b.key)));
  return out;
})()'''

DATENPFLEGE_JS = '''(async () => {
  const P = __PAYLOAD__;
  ''' + _HEAD + r'''
  const out = { updated: 0, errors: [] };
  const before = await readRows(); const byId = {}; before.forEach(r => { byId[r.id] = r; });
  for (const u of P.updates) {
    const r = byId[u.id];
    if (!r || String((r.values || {}).Quelle || '') !== u.quelle) { out.errors.push('uebersprungen ' + u.id); continue; }
    try {
      const ur = await c.mutate({ mutation: op('mutation', 'updateCustomRow', [['id', 'ID'], ['input', 'UpdateCustomRowInput']], [F('id')]), variables: { id: u.id, input: { values: { ...(r.values || {}), 'Warum offen': u.warum } } }, errorPolicy: 'all' });
      if (ur.data && ur.data.updateCustomRow) out.updated++; else out.errors.push(u.id + ': ' + (ur.errors || []).map(e => e.message).join('; ').slice(0, 160));
    } catch (e) { out.errors.push(String(e.message).slice(0, 160)); }
  }
  const after = await readRows(); const back = {}; after.forEach(r => { back[r.id] = r.values || {}; });
  out.verified = P.updates.filter(u => (back[u.id] || {})['Warum offen'] === u.warum).length;
  out.rows_before = before.length; out.rows_after = after.length;
  out.other_unchanged = before.filter(r => !P.updates.some(u => u.id === r.id)).every(r => JSON.stringify(back[r.id]) === JSON.stringify(r.values || {}));
  return out;
})()'''

KOMPAKT_READ_JS = '''(async () => {
  const P = __PAYLOAD__;
  ''' + _HEAD + r'''
  return { fields: await readFields(), rows: await readRows() };
})()'''

KOMPAKT_JS = '''(async () => {
  const P = __PAYLOAD__;
  ''' + _HEAD + r'''
  const out = { errors: [], updated: 0 };
  const before = await readFields();
  const keep = before.filter(f => P.keep.includes(f.key));
  if (!before.some(f => f.key === 'Details')) {
    const withD = before.concat([{ key: 'Details', type: 'string', required: false, enumValues: null, multipleSelection: false }]);
    const r1 = await c.mutate({ mutation: op('mutation', 'updateCustomTable', [['id', 'ID'], ['input', 'UpdateCustomTableInput']], [F('id')]), variables: { id: P.tableId, input: { fields: withD } }, errorPolicy: 'all' });
    if (!r1.data || !r1.data.updateCustomTable) { out.errors.push('Details anlegen: ' + (r1.errors || []).map(e => e.message).join('; ').slice(0, 200)); return out; }
  }
  for (const r of P.rows) {
    const ur = await c.mutate({ mutation: op('mutation', 'updateCustomRow', [['id', 'ID'], ['input', 'UpdateCustomRowInput']], [F('id')]), variables: { id: r.id, input: { values: r.values } }, errorPolicy: 'all' });
    if (ur.data && ur.data.updateCustomRow) out.updated++; else out.errors.push('Zeile ' + r.id + ': ' + (ur.errors || []).map(e => e.message).join('; ').slice(0, 160));
  }
  if (out.errors.length) return out;   // Spalten erst entfernen, wenn alle Zeilen umgeschrieben sind
  const now = await readFields();
  const order = P.keep; const rank = k => order.indexOf(k);
  const fields = now.filter(f => order.includes(f.key)).sort((a, b) => rank(a.key) - rank(b.key));
  const r2 = await c.mutate({ mutation: op('mutation', 'updateCustomTable', [['id', 'ID'], ['input', 'UpdateCustomTableInput']], [F('id')]), variables: { id: P.tableId, input: { fields } }, errorPolicy: 'all' });
  if (!r2.data || !r2.data.updateCustomTable) out.errors.push('Spalten kuerzen: ' + (r2.errors || []).map(e => e.message).join('; ').slice(0, 200));
  out.fields_after = (await readFields()).map(f => f.key);
  const rows = await readRows(); out.rows_after = rows.length;
  out.sample = rows.slice(0, 2).map(r => r.values);
  return out;
})()'''

READ_JS = '''(async () => {
  const P = __PAYLOAD__;
  ''' + _HEAD + r'''
  return (await readRows()).map(r => ({ id: r.id, values: r.values || {} }));
})()'''

WRITE_JS = '''(async () => {
  const P = __PAYLOAD__;
  ''' + _HEAD + r'''
  const out = { written: 0, errors: [] };
  const rows = await readRows(); const byId = {}; rows.forEach(r => { byId[r.id] = r; });
  const mk = r => { const m = /ev:([0-9a-f]{8}|zztest\d+)/.exec(String((r.values || {}).Quelle || '')); return m ? m[1] : null; };
  for (const u of P.updates) {
    const r = byId[u.id];
    if (!r || mk(r) !== u.marker) { out.errors.push('uebersprungen ' + u.marker); continue; }
    const add = { 'Rückmeldung': u.rueck }; if (u.status) add.Status = u.status;
    try {
      const ur = await c.mutate({ mutation: op('mutation', 'updateCustomRow', [['id', 'ID'], ['input', 'UpdateCustomRowInput']], [F('id')]), variables: { id: u.id, input: { values: { ...(r.values || {}), ...add } } }, errorPolicy: 'all' });
      if (ur.data && ur.data.updateCustomRow) out.written++; else out.errors.push(u.marker + ': ' + (ur.errors || []).map(e => e.message).join('; ').slice(0, 160));
    } catch (e) { out.errors.push(String(e.message).slice(0, 160)); }
  }
  const after = await readRows(); const back = {}; after.forEach(r => { back[r.id] = r.values || {}; });
  out.verified = P.updates.filter(u => (back[u.id] || {})['Rückmeldung'] === u.rueck).length;
  out.zuordnung_erhalten = P.updates.filter(u => (back[u.id] || {}).Zuordnung === ((byId[u.id] || {}).values || {}).Zuordnung).length;
  return out;
})()'''


# Auswahl je Zeile: 'Kandidat 1..8' (= Nummer in der Spalte 'Mögliche PO' DIESER Zeile, wahrscheinlichste zuerst) oder 'Info'. 'Zuordnung' bleibt freier Text (z. B. PO-ID, wenn die Bestellung nicht unter den Kandidaten ist).
INFO_OPT = "Info"
AUSWAHL_OPTS = [INFO_OPT] + ["Kandidat %d" % i for i in range(1, 9)]

DROPDOWN_JS = '''(async () => {
  const P = __PAYLOAD__;
  ''' + _HEAD + r'''
  const out = { errors: [], changed: false };
  const before = await readFields(); const rowsBefore = await readRows();
  const a = before.find(x => x.key === 'Auswahl'), z = before.find(x => x.key === 'Zuordnung');
  if (!z) { out.errors.push('Spalte Zuordnung fehlt'); return out; }
  const okA = a && a.type === 'dropdown' && JSON.stringify(a.enumValues || []) === JSON.stringify(P.options);
  const okZ = z.type === 'string';
  out.auswahl_vorhanden = !!a; out.zuordnung_typ = z.type;
  if ((okA && okZ) || !P.apply) { out.would_change = !(okA && okZ); return out; }
  let fields = before.map(x => x.key === 'Zuordnung' ? { key: x.key, type: 'string', required: false, enumValues: null, multipleSelection: false } : x);
  const def = { key: 'Auswahl', type: 'dropdown', required: false, enumValues: P.options, multipleSelection: false };
  fields = fields.some(x => x.key === 'Auswahl') ? fields.map(x => x.key === 'Auswahl' ? def : x) : fields.concat([def]);
  const r = await c.mutate({ mutation: op('mutation', 'updateCustomTable', [['id', 'ID'], ['input', 'UpdateCustomTableInput']], [F('id')]), variables: { id: P.tableId, input: { fields } }, errorPolicy: 'all' });
  if (!r.data || !r.data.updateCustomTable) { out.errors.push((r.errors || []).map(e => e.message).join('; ').slice(0, 200)); return out; }
  const after = await readFields(); const rowsAfter = await readRows();
  out.changed = true; out.keys_after = after.map(x => x.key);
  out.rows_unchanged = JSON.stringify(rowsBefore.map(r => [r.id, r.values])) === JSON.stringify(rowsAfter.map(r => [r.id, r.values]));
  return out;
})()'''


def auswahl_zu_zuordnung(rows):
    """Zeilen mit 'Auswahl' (und leerer 'Zuordnung') -> 'Zuordnung' = PO-ID des n-ten Kandidaten aus 'Mögliche PO' derselben Zeile bzw. 'Info'. Aendert nur die Kopie im Speicher."""
    for r in rows:
        v = r.get("values") or {}
        a = str(v.get("Auswahl") or "").strip()
        if not a or str(v.get("Zuordnung") or "").strip():
            continue
        if a.lower() == "info":
            v["Zuordnung"] = "Info"; continue
        m = re.fullmatch(r"Kandidat (\d+)", a)
        cands = re.findall(r"\d+\) (PO\d{2}-\d{3})", str(v.get("Mögliche PO") or ""))
        v["Zuordnung"] = cands[int(m.group(1)) - 1] if m and 0 < int(m.group(1)) <= len(cands) else a
    return rows


def sync_dropdown(orders=None, runner=None, apply=True, cfg=None):
    cfg = cfg or json.loads(klaerfaelle.CFG.read_text())
    if runner is None:
        from plm_intake.barcodes import run_js as runner
    pay = json.dumps({"tableId": cfg["tableId"], "options": AUSWAHL_OPTS, "apply": bool(apply)}, ensure_ascii=False)
    return runner(DROPDOWN_JS.replace("__PAYLOAD__", pay)) or {}


def marker_of(values):
    m = re.search(r"ev:([0-9a-f]{8}|zztest\d+)", str((values or {}).get("Quelle") or ""))
    return m.group(1) if m else None


def parse(value):
    """-> (kind 'info'|'order', text, nur)"""
    t = str(value or "").strip()
    nur = bool(NUR.search(t))
    t = NUR.sub("", t).strip()
    return ("info" if t.lower() == "info" else "order"), t, nur


def resolve_order(text, orders):
    """-> (order|None, fehler|None). PO-ID, #Nr, Titel oder Order-ID; abgeschlossene/Test-Orders werden abgelehnt."""
    t = re.sub(r"[`*_\s]+", " ", str(text or "")).strip()
    live = [o for o in orders if not events.TEST_ORDER.search(str(o.get("title") or ""))]
    po = po_ids.norm_po(t)
    if po:
        hit, what = [o for o in live if (po_ids.po_id(o) or "").upper() == po.upper()], "PO-ID " + po
    elif re.fullmatch(r"#\s*\d+", t):
        n = re.sub(r"\D", "", t); hit, what = [o for o in live if str(o.get("orderNumber")) == n], t
    else:
        hit, what = [o for o in live if o.get("id") == t or core.norm(o.get("title")) == core.norm(t)], "'%s'" % t[:40]
    if not hit:
        return None, "%s unbekannt" % what
    if len(hit) > 1:
        return None, "%s mehrdeutig (%d Orders)" % (what, len(hit))
    if events._status(hit[0]) in events.ACTIVE_NOT:
        return None, "%s ist abgeschlossen" % what
    return hit[0], None


def _thread_vendor(e):
    """(Thread-ID, normalisierter Lieferant) eines Ereignisses; (None, None), wenn eines von beiden fehlt."""
    if not e:
        return None, None
    t = (e.get("_mail") or {}).get("thread")
    v = core.norm(e.get("vendor") or "") if events.vendor_plausible(e.get("vendor")) else ""
    return (t, v) if t and v else (None, None)


def plan(rows, orders, ev_ov, aliases, evt_by_marker=None, only_marker=None, max_rows=MAX_ROWS):
    """rows = [{id, values}] der ganzen Tabelle. Rein rechnerisch.
    -> {ev_ov (neu), aliases, neu_alias, konflikte, updates [{id, marker, rueck, status}], angewendet, abgelehnt, uebersprungen, offen_ungelesen}"""
    evt_by_marker = evt_by_marker or {}
    ev_ov = dict(ev_ov)
    res = {"updates": [], "angewendet": 0, "abgelehnt": 0, "schon": 0, "ungelesen": 0, "neu_alias": [], "konflikte": []}
    inputs = [r for r in rows if str((r["values"] or {}).get("Zuordnung") or "").strip() and str((r["values"] or {}).get("Status") or "offen") == "offen"]
    if only_marker:
        inputs = [r for r in inputs if marker_of(r["values"]) == only_marker]
    res["ungelesen"] = max(0, len(inputs) - max_rows)
    inputs = inputs[:max_rows]
    has_input = {r["id"] for r in rows if str((r["values"] or {}).get("Zuordnung") or "").strip()}
    all_orders = [o for o in orders]
    by_id = {o["id"]: o for o in all_orders}
    pairs, handled = [], set()

    def feedback(r, mk, text, status=None):
        if str(r["values"].get("Rückmeldung") or "") != text or status:
            res["updates"].append({"id": r["id"], "marker": mk, "rueck": text, "status": status})

    for r in inputs:
        v = r["values"]; mk = marker_of(v)
        kind, text, nur = parse(v.get("Zuordnung"))
        if not mk:
            res["abgelehnt"] += 1; feedback(r, mk, "abgelehnt: Zeile ohne Marker (ev:...) in 'Quelle'"); continue
        order, err = (None, None)
        if kind == "order":
            order, err = resolve_order(text, all_orders)
            if err:
                res["abgelehnt"] += 1; feedback(r, mk, "abgelehnt: " + err); continue
        val = events.INFO_OVERRIDE if kind == "info" else order["id"]
        mid = str(v.get("Mail-ID") or "").strip()
        group = [r] if (nur or not mid) else [x for x in rows if str(x["values"].get("Mail-ID") or "").strip() == mid and marker_of(x["values"])
                                              and str(x["values"].get("Status") or "offen") == "offen" and (x["id"] == r["id"] or x["id"] not in has_input)]
        if kind == "order" and not nur:   # Mail-Verlauf: Zeilen desselben Gmail-Threads mit gleichem Lieferanten gehen mit (nur bei Order-Zuordnung, nie bei info)
            t0, v0 = _thread_vendor(evt_by_marker.get(mk))
            if t0 and v0:
                have = {x["id"] for x in group}
                group += [x for x in rows if x["id"] not in have and marker_of(x["values"]) and str(x["values"].get("Status") or "offen") == "offen" and x["id"] not in has_input
                          and _thread_vendor(evt_by_marker.get(marker_of(x["values"]))) == (t0, v0)]
        cur = ev_ov.get(mk)
        if cur is not None and cur != val:
            res["abgelehnt"] += 1; feedback(r, mk, "abgelehnt: Konflikt, Ereignis hat schon eine andere Entscheidung (%s)" % cur); continue
        n, skip = 0, 0
        for x in group:
            xm = marker_of(x["values"])
            if xm in handled:
                continue
            c2 = ev_ov.get(xm)
            if c2 is not None and c2 != val:
                skip += 1; continue
            if c2 is None:
                ev_ov[xm] = val; n += 1
            handled.add(xm)
            if order is not None:
                for k in alias_learn.event_idents(evt_by_marker.get(xm) or {}):
                    if alias_learn.valid(k, order, (), all_orders):
                        pairs.append((k, order["id"], "Zuordnung-Tabelle " + xm))
        ziel = "kein Bestellbezug" if kind == "info" else (po_ids.po_id(order) or order["title"])
        if n == 0 and not skip:
            res["schon"] += 1; continue
        res["angewendet"] += 1
        feedback(r, mk, "angewendet: %s, %d Ereignis%s%s" % (ziel, n, "se" if n != 1 else "", ", %d wegen Konflikt uebersprungen" % skip if skip else ""),
                 status="erledigt" if kind == "info" else None)
    work, new, conf = alias_learn.merge(aliases, pairs, all_orders, apply=False)
    res.update({"ev_ov": ev_ov, "aliases": work, "neu_alias": new, "konflikte": conf})
    return res


def _write_json(path, data):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)); tmp.replace(p)


def run(ctx_orders, intake, evt=(), runner=None, apply=False, only_marker=None, backup_dir=None, cfg=None):
    """Tabelle lesen, planen, bei apply: Backup der betroffenen Zeilen, Overrides/Aliase schreiben, 'Rückmeldung' schreiben, zuruecklesen.
    -> dict(angewendet, abgelehnt, ... , fehler[])"""
    intake = Path(intake)
    cfg = cfg or json.loads(klaerfaelle.CFG.read_text())
    if runner is None:
        from plm_intake.barcodes import run_js as runner
    pay = lambda **k: json.dumps(dict(tableId=cfg["tableId"], **k), ensure_ascii=False)
    dd = {}
    if apply:
        try:
            dd = sync_dropdown(ctx_orders, runner, True, cfg)   # Auswahlliste aktuell halten; Fehler brechen nichts ab
        except Exception as e:
            dd = {"errors": [str(e)[:160]]}
    rows = auswahl_zu_zuordnung(runner(READ_JS.replace("__PAYLOAD__", pay())) or [])
    ev_ov = events.load_event_overrides(intake)
    try:
        aliases = json.load(open(intake / "po_aliases.json"))
    except (OSError, ValueError):
        aliases = {}
    p = plan(rows, ctx_orders, ev_ov, aliases, {events.marker(e): e for e in evt}, only_marker)
    out = {k: p[k] for k in ("angewendet", "abgelehnt", "schon", "ungelesen", "neu_alias", "konflikte")}
    out["updates"] = p["updates"]; out["fehler"] = []; out["dry"] = not apply; out["dropdown"] = dd if isinstance(dd, dict) else {}
    if not apply or not p["updates"] and p["ev_ov"] == ev_ov:
        return out
    bk = Path(backup_dir) if backup_dir else ROOT / "output" / "backup"
    bk.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    ids = {u["id"] for u in p["updates"]}
    (bk / ("klaerfaelle_zuordnung_%s.json" % ts)).write_text(json.dumps({"zeilen": [r for r in rows if r["id"] in ids], "event_overrides_vorher": ev_ov, "po_aliases_vorher": aliases}, ensure_ascii=False, indent=1))
    _write_json(intake / "event_overrides.json", p["ev_ov"])
    if p["neu_alias"] or p["konflikte"]:
        _write_json(intake / "po_aliases.json", p["aliases"])
    chk = events.load_event_overrides(intake)
    if any(chk.get(k) != v for k, v in p["ev_ov"].items()):
        out["fehler"].append("event_overrides nach dem Schreiben nicht wie geplant"); return out
    if p["updates"]:
        w = runner(WRITE_JS.replace("__PAYLOAD__", pay(updates=p["updates"]))) or {}
        out["fehler"] += w.get("errors") or []
        if w.get("verified") != len(p["updates"]):
            out["fehler"].append("Zuruecklesen Rueckmeldung: %s von %d" % (w.get("verified"), len(p["updates"])))
        if w.get("zuordnung_erhalten") != len(p["updates"]):
            out["fehler"].append("Zuordnung veraendert (sollte unveraendert sein)")
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--spalten", action="store_true")
    ap.add_argument("--kompakt", action="store_true", help="Tabelle auf die wichtigsten Spalten kuerzen (Rest in 'Details'); Trockenlauf ohne --apply, mit Sicherung aller Zeilen")
    ap.add_argument("--datenpflege", action="store_true", help="Zeilen ohne Mail-Bezug (Zahlungsplan, Datenabgleich) mit 'Datenpflege:' vor 'Warum offen' markieren; Trockenlauf ohne --apply, Sicherung aller Zeilen")
    ap.add_argument("--dropdown", action="store_true", help="Spalte 'Zuordnung' als Auswahlliste (Info + laufende Orders) einrichten/aktualisieren; Trockenlauf ohne --apply")
    ap.add_argument("--reihenfolge", action="store_true", help="Spalten in die Reihenfolge fuer den Menschen bringen (Trockenlauf ohne --apply)")
    ap.add_argument("--nur-marker")
    a = ap.parse_args(argv)
    cfg = json.loads(klaerfaelle.CFG.read_text())
    from plm_intake.barcodes import run_js
    if a.kompakt:
        import datetime
        cur = run_js(KOMPAKT_READ_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"]})))
        bk = ROOT / "output" / "backup" / ("klaerfaelle_vor_kompakt_%s.json" % datetime.date.today().isoformat())
        bk.parent.mkdir(parents=True, exist_ok=True); bk.write_text(json.dumps(cur, ensure_ascii=False, indent=1))
        rows = [{"id": r["id"], "values": klaerfaelle.kompakt(r.get("values") or {})} for r in cur["rows"]]
        print("Zeilen: %d | Sicherung: %s | Beispiel neu: %s" % (len(rows), bk, json.dumps(rows[0]["values"], ensure_ascii=False)[:400] if rows else "-"))
        if not a.apply:
            return 0
        r = run_js(KOMPAKT_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"], "rows": rows, "keep": list(REIHENFOLGE)}, ensure_ascii=False)))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if not r.get("errors") else 1
    if a.datenpflege:   # Zeilen, die keine Mail-Faelle sind, erkennbar markieren ('Datenpflege: ' vor 'Warum offen'); keine Zeile wird entfernt
        import datetime
        cur = run_js(KOMPAKT_READ_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"]})))
        ups = [{"id": r["id"], "quelle": str((r.get("values") or {}).get("Quelle") or ""), "warum": klaerfaelle.datenpflege(r.get("values") or {})["Warum offen"]}
               for r in cur["rows"] if klaerfaelle.ist_datenpflege(r.get("values")) and not str((r.get("values") or {}).get("Warum offen") or "").startswith(klaerfaelle.DATENPFLEGE)]
        bk = ROOT / "output" / "backup" / ("klaerfaelle_vor_datenpflege_%s.json" % datetime.date.today().isoformat())
        print("Zeilen gesamt: %d | davon neu als Datenpflege zu markieren: %d | Sicherung: %s" % (len(cur["rows"]), len(ups), bk if a.apply else "(erst mit --apply)"))
        for u in ups[:20]:
            print("  -", u["quelle"][:60], "->", u["warum"][:80])
        if not a.apply or not ups:
            return 0
        bk.parent.mkdir(parents=True, exist_ok=True); bk.write_text(json.dumps(cur, ensure_ascii=False, indent=1))
        r = run_js(DATENPFLEGE_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"], "updates": ups}, ensure_ascii=False)))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if not r.get("errors") and r.get("verified") == len(ups) and r.get("other_unchanged") else 1
    if a.dropdown:
        print("Optionen Auswahl:", AUSWAHL_OPTS)
        r = sync_dropdown(None, None, a.apply)
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if not r.get("errors") else 1
    if a.reihenfolge:
        r = run_js(ORDER_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"], "order": list(REIHENFOLGE), "apply": a.apply})))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if not r.get("errors") else 1
    if a.spalten:
        r = run_js(COLS_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"], "cols": list(NEW_COLS), "apply": a.apply})))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if not r.get("errors") else 1
    from plm_intake.context import load_context, add_po_numbers
    ctx = load_context(); add_po_numbers(ctx)
    r = run(ctx["orders"], ROOT / "output" / "intake", (), apply=a.apply, only_marker=re.sub(r"^ev:", "", a.nur_marker or "") or None)
    print(json.dumps(r, ensure_ascii=False, indent=1)); return 1 if r["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
