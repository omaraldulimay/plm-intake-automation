(async () => {
  // Erzeugt von plm_intake/payments_plan.py. Ersetzt das GANZE payments-Array je Order (UpdateOrder ersetzt, haengt nicht an).
  // Vor dem Schreiben: Vorzustand der Order muss dem geplanten Vorzustand entsprechen (sonst uebersprungen, 'skipped_changed').
  // Nach dem Schreiben: zuruecklesen; alles ausser payments muss gleich sein, payments == Plan, Summe == totalCost (+-0,01, leere Liste erlaubt).
  // Bricht beim ersten Fehler/jeder Abweichung ab. DRY=true schreibt nichts. Voraussetzung: chrome_order_helpers.js geladen.
  const DRY = __DRY__;
  const PLAN = __PLAN__;
  const out = [];
  if (typeof window.__fetchOrder !== 'function' || typeof window.__updOrder !== 'function') return [{ fatal: 'Helfer nicht geladen (chrome_order_helpers.js zuerst)' }];
  const clean = a => JSON.parse(JSON.stringify(a, (k, v) => (k === '__typename' ? undefined : v)));
  const r2 = x => Math.round((x + Number.EPSILON) * 100) / 100;
  const skel = o => JSON.stringify({
    t: o.title, n: o.totalNumberOfPieces, c: o.totalCost, cur: o.currency, notes: o.notes, po: o.poNumber, ex: o.exFactoryExpectedDate, etd: o.etdEstimatedDate,
    m: o.manufacturer && o.manufacturer.id, st: o.status && o.status.status,
    items: (o.items || []).map(i => ({ n: i.name, p: i.product && i.product.id || null, v: (i.variants || []).map(v => ({ n: v.name, id: v.variantId || null, a: (v.amounts || []).map(a => [a.key, a.quantity, a.price, a.cost]) })) })) });
  const sameBefore = (cur, bef) => cur.length === bef.length && cur.every((p, i) => p.name === bef[i].name && p.status === bef[i].status && Math.abs((p.amount || 0) - (bef[i].amount || 0)) < 0.005 && String(p.dueDate == null ? '' : p.dueDate) === String(bef[i].dueDate == null ? '' : bef[i].dueDate));
  for (const p of PLAN) {
    try {
      const b = await window.__fetchOrder(p.id);
      if (!b.d) { out.push({ title: p.title, error: 'nicht lesbar' }); break; }
      const o = clean(b.d);
      if (!sameBefore(o.payments || [], p.before)) { out.push({ title: p.title, skipped_changed: 'Zahlungen im PLM weichen vom geplanten Vorzustand ab (zwischenzeitlich geaendert), nichts geschrieben' }); continue; }
      if (Math.abs((o.totalCost || 0) - p.total) > 0.01) { out.push({ title: p.title, skipped_changed: 'Gesamtwert geaendert (' + o.totalCost + ' statt ' + p.total + ')' }); continue; }
      const sum = r2(p.payments.reduce((s, x) => s + (x.amount || 0), 0));
      if (p.payments.length && Math.abs(sum - r2(o.totalCost || 0)) > 0.01 && p.kind === 'plan') { out.push({ title: p.title, error: 'Plansumme ' + sum + ' != totalCost ' + o.totalCost }); break; }
      if (DRY) { out.push({ title: p.title, dry: true, kind: p.kind, rows: p.payments.length, sum }); continue; }
      const r = await window.__updOrder(p.id, { payments: p.payments });
      if (r.err && (Array.isArray(r.err) ? r.err.length : r.err)) { out.push({ title: p.title, error: r.err, unsure: true }); break; }
      const a = await window.__fetchOrder(p.id);
      const after = clean(a.d);
      const same = skel(after) === skel(o);
      const ap = after.payments || [];
      const payOk = ap.length === p.payments.length && ap.every((x, i) => x.name === p.payments[i].name && x.status === p.payments[i].status && Math.abs((x.amount || 0) - (p.payments[i].amount || 0)) < 0.005
        && (x.terms || '') === (p.payments[i].terms || '') && ((p.payments[i].dueDate == null) ? (x.dueDate == null || x.dueDate === '') : Number(x.dueDate) === Number(p.payments[i].dueDate)));
      const asum = r2(ap.reduce((s, x) => s + (x.amount || 0), 0));
      const sumOk = ap.length === 0 || Math.abs(asum - r2(after.totalCost || 0)) <= 0.01 || p.kind === 'paid';
      const rec = { title: p.title, kind: p.kind, rows: ap.length, sum: asum, totalCost: after.totalCost, dataUnchanged: same, paymentsOk: payOk, sumOk };
      out.push(rec);
      if (!same || !payOk || !sumOk) { rec.ABBRUCH = 'Abweichung nach Update: Backup output/backup/payments_vor_*.json pruefen'; break; }
    } catch (e) { out.push({ title: p.title, error: String(e && e.message || e).slice(0, 300), unsure: true }); break; }
  }
  return out;
})()
