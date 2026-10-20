"""Klaerfaelle der Einpflege im PLM (Custom Table "Klärfälle Einpflege", Kategorie = Lieferant).

Nur echte, bestellbezogene Faelle: Ereignis-Typ Versand/Termin/Zahlung/Aenderung/Verzoegerung/Qualitaet, nicht zuordenbar
(keine passende PO oder mehrere moeglich), und der Lieferant ist erkannt ODER eine PO-/Stylenummer ist genannt.
Nicht aufgenommen: Muster/Allgemeines ohne Bestellung, Paket-/Zolldienste, Fremdes ohne Lieferant und Nummer (z. B. Abo-Rechnungen).
Je Fall eine Zeile mit Marker ev:<hash> (keine Doppelten). Wird ein Fall spaeter einer PO zugeordnet, setzt der Lauf ihn auf "erledigt".
Schreibt nie in Bestellungen; loescht nie Zeilen.

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
  const out = { created: 0, closed: 0, categories: 0, errors: [] };
  const tq = await c.query({ query: op('query', 'customTable', [['id', 'ID']], [F('id'), F('categories', [F('id'), F('name')])]), variables: { id: P.tableId }, fetchPolicy: 'no-cache', errorPolicy: 'all' });
  const cats = {}; ((tq.data && tq.data.customTable && tq.data.customTable.categories) || []).forEach(x => { cats[x.name] = x.id; });
  const rq = await c.query({ query: op('query', 'customRowsByTable', [['tableId', 'ID']], [F('id'), F('categoryId'), F('values')]), variables: { tableId: P.tableId }, fetchPolicy: 'no-cache', errorPolicy: 'all' });
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
  const resolved = new Set(P.resolved);
  for (const r of rows) {
    const m = mk(r);
    if (!m || !resolved.has(m) || (r.values || {}).Status !== 'offen') continue;
    try {
      const ur = await c.mutate({ mutation: op('mutation', 'updateCustomRow', [['id', 'ID'], ['input', 'UpdateCustomRowInput']], [F('id')]), variables: { id: r.id, input: { values: { ...r.values, Status: 'erledigt' } } }, errorPolicy: 'all' });
      if (ur.data && ur.data.updateCustomRow) out.closed++; else out.errors.push('Abhaken ' + m + ': ' + (ur.errors || []).map(e => e.message).join('; ').slice(0, 160));
    } catch (e) { out.errors.push(String(e.message).slice(0, 160)); }
  }
  const after = await c.query({ query: op('query', 'customRowsByTable', [['tableId', 'ID']], [F('id'), F('values')]), variables: { tableId: P.tableId }, fetchPolicy: 'no-cache', errorPolicy: 'all' });
  out.rows_total = ((after.data && after.data.customRowsByTable) || []).length;
  out.open_total = ((after.data && after.data.customRowsByTable) || []).filter(r => (r.values || {}).Status === 'offen').length;
  return out;
})()'''


def sync(pl, ctx, vendor_aliases=None, runner=None):
    """Neue Klaerfaelle eintragen, zugeordnete abhaken. pl = events.plan(...); runner(js) -> Ergebnis (Browser)."""
    cfg = json.loads(CFG.read_text())
    dom = events.domain_vendors(ctx["vendors"])
    rows = select(pl["unmatched"], ctx["vendors"], vendor_aliases, dom, mail_dirs())
    resolved = sorted({l["marker"] for o in pl["orders"] for l in o["lines"]})
    js = SYNC_JS.replace("__PAYLOAD__", json.dumps({"tableId": cfg["tableId"], "brandId": cfg["brandId"], "rows": rows, "resolved": resolved, "fill": list(NEU)}, ensure_ascii=False))
    if runner is None:
        from plm_intake.barcodes import run_js as runner
    return rows, runner(js)


def main(argv=None):
    import argparse
    import os
    from plm_intake import ledger
    from plm_intake.context import load_context, add_po_numbers
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=os.path.expanduser("~/Library/CloudStorage/kontakt@firma.example/Meine Ablage/Inbox"))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    intake = ROOT / "output" / "intake"
    led = ledger.load(intake / "ledger.json")
    evs = [f for f in sorted(Path(a.inbox).glob("*_events.json")) if not ledger.is_done(led, f)]
    ctx = load_context(); add_po_numbers(ctx)
    al = json.load(open(intake / "vendor_aliases.json")) if (intake / "vendor_aliases.json").exists() else {}
    poal = json.load(open(intake / "po_aliases.json")) if (intake / "po_aliases.json").exists() else {}
    pl = events.plan(events.load_events(evs), ctx["orders"], ctx["vendors"], poal, al, vendor_only=True, products=ctx["products"], style_aliases=ctx.get("style_aliases"))
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
