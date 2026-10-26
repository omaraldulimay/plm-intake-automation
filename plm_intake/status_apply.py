"""Status setzen laut Freigabeliste (output/phase2/B24/status_freigabe.csv, Spalte Freigabe = ja) bzw. automatisch (nur Sicherheit hoch, nur mit STATUS_AUTO=1).

Regeln: nur VORWAERTS, nie ab Complete, Ist-Status muss noch dem der Liste entsprechen (sonst uebersprungen), Statusobjekt (id/color/order) stammt aus dem PLM.
Schreiben per App-GraphQL im Browser (window.__updOrder(id,{status})). Vorzustand aller betroffenen Orders: output/backup/status_vor_<Zeit>.json (VOR dem Schreiben).
Zuruecklesen je Order: Status = Ziel UND alles andere unveraendert (Titel, Summe, Menge, Lieferant, Positionen, Zahlungen). Bei Abweichung stoppt der Lauf.
Dry-Run ist Standard:  .venv/bin/python -m plm_intake.status_apply <csv> [--apply]
"""
import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plm_intake import status_rules as sr  # noqa: E402

BROWSER = Path(__file__).resolve().parent / "browser"
BACKUP_DIR = ROOT / "output" / "backup"
MAX_AUTO = 10
MAX_MANUAL = 60
AUTO_ENV = "STATUS_AUTO"

JS_READ = "(async()=>{const out={};for(const id of __IDS__){const b=await window.__fetchOrder(id);out[id]=b&&b.d?JSON.parse(JSON.stringify(b.d,(k,v)=>k==='__typename'?undefined:v)):null;}return out;})()"

JS_WRITE = r'''(async () => {
  const PLAN = __PLAN__;
  const out = [];
  if (typeof window.__fetchOrder !== 'function' || typeof window.__updOrder !== 'function') return [{ fatal: 'Helfer nicht geladen' }];
  const clean = a => JSON.parse(JSON.stringify(a, (k, v) => (k === '__typename' ? undefined : v)));
  const core = o => JSON.stringify({ t: o.title, c: o.totalCost, n: o.totalNumberOfPieces, m: o.manufacturer && o.manufacturer.id, notes: o.notes || '',
    items: (o.items || []).map(i => ({ n: i.name, p: i.product && i.product.id || null, v: (i.variants || []).map(v => ({ n: v.name, id: v.variantId || null, a: (v.amounts || []).map(a => [a.key, a.quantity, a.price, a.cost]) })) })),
    pay: (o.payments || []).map(p => [p.name, p.status, p.amount, p.dueDate]) });
  for (const p of PLAN) {
    try {
      const b = await window.__fetchOrder(p.id);
      if (!b.d) { out.push({ title: p.title, error: 'nicht lesbar' }); break; }
      const o = clean(b.d);
      const cur = o.status || {};
      if (cur.status !== p.from || cur.status === 'Complete' || (cur.order || 0) >= p.to.order) { out.push({ title: p.title, skipped: 'Status inzwischen ' + cur.status }); continue; }
      const r = await window.__updOrder(p.id, { status: p.to });
      if (r.err && (Array.isArray(r.err) ? r.err.length : r.err)) { out.push({ title: p.title, error: r.err, unsure: true }); break; }
      const a = await window.__fetchOrder(p.id);
      const after = clean(a.d);
      const statusOk = !!(after.status && after.status.status === p.to.status);
      const same = core(after) === core(o);
      const rec = { title: p.title, from: p.from, to: p.to.status, statusOk, dataUnchanged: same };
      out.push(rec);
      if (!statusOk || !same) { rec.ABBRUCH = 'Abweichung nach Update: Backup output/backup/status_vor_*.json pruefen'; break; }
    } catch (e) { out.push({ title: p.title, error: String(e && e.message || e).slice(0, 300), unsure: true }); break; }
  }
  return out;
})()'''


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(2048); f.seek(0)
        delim = ";" if sample.count(";") >= sample.count(",") else ","
        return list(csv.DictReader(f, delimiter=delim))


def approved(rows):
    """Freigegebene Aenderungszeilen (Freigabe == ja, Art == Aenderung)."""
    return [r for r in rows if str(r.get("Freigabe") or "").strip().lower() in ("ja", "j", "yes", "x") and str(r.get("Art") or "Aenderung").strip() == "Aenderung"]


def plan(rows, orders, status_objs, limit=MAX_MANUAL):
    """rows: Dicts mit Order-ID/Aktuell/Ziel (CSV-Spalten). -> (aenderungen[{id,title,from,to}], uebersprungen[str])."""
    by_id = {o["id"]: o for o in orders}
    todo, skip = [], []
    for r in rows:
        oid, ziel, soll = r.get("Order-ID"), str(r.get("Ziel") or "").strip(), str(r.get("Aktuell") or "").strip()
        o = by_id.get(oid)
        if not o:
            skip.append("%s: Order nicht im PLM" % (r.get("Order") or oid)); continue
        cur = sr.status_name(o)
        if cur != soll:
            skip.append("%s: Status inzwischen %s statt %s, uebersprungen" % (o["title"], cur, soll)); continue
        if cur == "Complete" or sr.STATUS_ORDER.get(ziel, 0) <= sr.STATUS_ORDER.get(cur, 99):
            skip.append("%s: %s -> %s waere kein Vorwaertsschritt" % (o["title"], cur, ziel)); continue
        if ziel not in status_objs:
            skip.append("%s: Statusobjekt '%s' im PLM unbekannt" % (o["title"], ziel)); continue
        if any(t["id"] == oid for t in todo):
            continue
        if len(todo) >= limit:
            skip.append("%s: Limit %d je Lauf, naechster Lauf" % (o["title"], limit)); continue
        todo.append({"id": oid, "title": o["title"], "from": cur, "to": status_objs[ziel]})
    return todo, skip


def run_js(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    r = subprocess.run(["node", str(BROWSER / "run_in_plm.js"), f.name], capture_output=True, text=True, cwd=str(BROWSER), timeout=900)
    if r.returncode:
        raise RuntimeError("Browser-Lauf gescheitert: " + (r.stderr or r.stdout)[-300:])
    return json.loads(r.stdout)


def backup(before, todo, now=None):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    p = BACKUP_DIR / ("status_vor_%s.json" % (now or dt.datetime.now()).strftime("%Y-%m-%d_%H%M%S"))
    p.write_text(json.dumps({"plan": todo, "orders": before}, ensure_ascii=False, indent=1))
    return p


def verify(todo, res):
    """-> (gesetzt, fehler[]). Gesetzt zaehlt nur, wenn Zuruecklesen Status = Ziel UND Rest unveraendert meldet."""
    done = {r.get("title"): r for r in res if isinstance(r, dict)}
    ok, errs = 0, []
    for r in res:
        if isinstance(r, dict) and r.get("fatal"):
            errs.append(str(r["fatal"]))
    for t in todo:
        r = done.get(t["title"])
        if r is None:
            errs.append("%s: nicht versucht (Lauf gestoppt)" % t["title"])
        elif r.get("skipped"):
            continue
        elif r.get("error") or r.get("ABBRUCH") or r.get("statusOk") is not True or r.get("dataUnchanged") is not True:
            errs.append("%s: %s" % (t["title"], r.get("error") or r.get("ABBRUCH") or "Zuruecklesen unstimmig"))
        else:
            ok += 1
    return ok, errs


def execute(todo, apply, runner=run_js, backup_fn=backup):
    """-> (zeilen, ergebnis{gesetzt,fehler,plan}). Trockenlauf liest/schreibt nichts."""
    res = {"gesetzt": 0, "fehler": 0, "plan": todo}
    L = ["- %s: %s" % (t["title"], "%s -> %s" % (t["from"], t["to"]["status"])) for t in todo]
    if not apply or not todo:
        return (["- (Trockenlauf) nichts geschrieben"] if not apply else []) + L, res
    before = runner(JS_READ.replace("__IDS__", json.dumps([t["id"] for t in todo])))
    L.append("- Backup: %s" % backup_fn(before, todo))
    out = runner(JS_WRITE.replace("__PLAN__", json.dumps(todo, ensure_ascii=False)))
    ok, errs = verify(todo, out)
    res.update(gesetzt=ok, fehler=len(errs))
    L.append("- Status gesetzt %d, Fehler %d" % (ok, len(errs)))
    L += ["- FEHLER %s" % e for e in errs[:8]]
    return L, res


def auto_enabled(env=None):
    return str((env if env is not None else os.environ).get(AUTO_ENV, "")).strip() == "1"


def auto(orders, shipments, status_objs, apply, event_status=None, env=None, runner=run_js, backup_fn=backup, today=None):
    """Taeglicher Schritt fuer auto_run. -> (zeilen, {vorschlaege, gesetzt, fehler, auto}). Setzt nur bei apply UND STATUS_AUTO=1, nur Sicherheit hoch, max. MAX_AUTO."""
    rows = sr.evaluate(orders, shipments, today=today, event_status=event_status)
    prop = [r for r in rows if r["art"] == "Aenderung"]
    res = {"vorschlaege": len(prop), "gesetzt": 0, "fehler": 0, "auto": auto_enabled(env)}
    L = ["- Vorschlaege: %d (hoch %d, mittel %d, niedrig %d), davon automatisch zulaessig: %d | STATUS_AUTO %s" % (
        len(prop), *(len([r for r in prop if r["sicherheit"] == s]) for s in ("hoch", "mittel", "niedrig")), len(sr.auto_candidates(rows)), "AN" if res["auto"] else "AUS (nichts gesetzt)")]
    if not (apply and res["auto"]):
        return L, res
    csv_rows = [{"Order-ID": r["order_id"], "Order": r["title"], "Aktuell": r["aktuell"], "Ziel": r["ziel"]} for r in sr.auto_candidates(rows)]
    todo, skip = plan(csv_rows, orders, status_objs, limit=MAX_AUTO)
    L += ["- uebersprungen: %s" % s for s in skip[:5]]
    L2, r2 = execute(todo, True, runner, backup_fn)
    res.update(gesetzt=r2["gesetzt"], fehler=r2["fehler"])
    return L + L2, res


def status_objects(orders):
    from plm_intake import events
    base = {}
    try:
        base = json.loads((ROOT / "output" / "intake" / "order_statuses.json").read_text())
    except (OSError, ValueError):
        pass
    base.update(events.status_objects(orders))   # frischer Stand aus dem PLM schlaegt die Datei
    return base


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    import plm_client
    from plm_intake.context import fetch_all
    orders = fetch_all(plm_client.call, "orders")
    rows = approved(read_csv(a.csv))
    todo, skip = plan(rows, orders, status_objects(orders))
    print("Freigegebene Zeilen: %d, umsetzbar: %d" % (len(rows), len(todo)))
    for s in skip:
        print("- uebersprungen: " + s)
    L, res = execute(todo, a.apply)
    print("\n".join(L))
    return 1 if res["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
