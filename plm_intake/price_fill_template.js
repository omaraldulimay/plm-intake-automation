(async () => {
  // Erzeugt von plm_intake/price_fill.py. Traegt Stueckpreise NUR in Positionen nach, deren Preis noch ueberall 0 ist (nie vorhandene Preise > 0).
  // Aendert Stueckpreis, Kosten je Menge, Gesamtsumme und haengt eine Notizzeile (Marker pf:<hash>, wiederholbar) an. DRY=true schreibt nichts.
  // Voraussetzung: chrome_order_helpers.js geladen. Bricht beim ersten Fehler oder jeder Abweichung ab.
  const DRY = __DRY__;
  const PLAN = __PLAN__;
  const out = [];
  if (typeof window.__fetchOrder !== 'function' || typeof window.__updOrder !== 'function') return [{ fatal: 'Helfer nicht geladen (chrome_order_helpers.js zuerst)' }];
  const clean = a => JSON.parse(JSON.stringify(a, (k, v) => (k === '__typename' ? undefined : v)));
  const r2 = x => Math.round((x + Number.EPSILON) * 100) / 100;
  // Vergleichsbild ohne Preise/Kosten/Summe/Notizen: alles andere muss gleich bleiben
  const skel = o => JSON.stringify({
    t: o.title, n: o.totalNumberOfPieces, m: o.manufacturer && o.manufacturer.id,
    items: (o.items || []).map(i => ({ n: i.name, p: i.product && i.product.id || null, v: (i.variants || []).map(v => ({ n: v.name, id: v.variantId || null, a: (v.amounts || []).map(a => [a.key, a.quantity]) })) })),
    pay: (o.payments || []).map(p => [p.name, p.status, p.amount, p.dueDate]) });
  for (const p of PLAN) {
    try {
      const b = await window.__fetchOrder(p.id);
      if (!b.d) { out.push({ title: p.title, error: 'nicht lesbar' }); break; }
      const o = clean(b.d);
      if ((o.notes || '').indexOf('pf:' + p.marker) >= 0) { out.push({ title: p.title, unchanged: true, why: 'schon nachgetragen' }); continue; }
      const items = clean(o.items).map(it => ({ ...it, product: it.product ? it.product.id : undefined }));
      let n = 0;
      for (const c of p.cells) {
        const it = items[c.item], v = it && it.variants && it.variants[c.variant];
        if (!it || it.name !== c.iname || !v || v.name !== c.vname) throw new Error('Position ' + c.item + '/' + c.variant + ' hat sich geaendert');
        if (v.amounts.some(a => a.price)) throw new Error('Position ' + c.iname + ' ' + c.vname + ' hat schon einen Preis: nicht ueberschrieben');
        const q = v.amounts.reduce((s, a) => s + (a.quantity || 0), 0);
        if (Math.abs(q - c.qty) > 0.0001) throw new Error('Menge ' + c.iname + ' ' + c.vname + ' hat sich geaendert');
        v.amounts = v.amounts.map(a => ({ ...a, price: c.price, cost: r2((a.quantity || 0) * c.price) })); n++;
      }
      const total = r2(items.reduce((s, it) => s + (it.variants || []).reduce((s2, v) => s2 + (v.amounts || []).reduce((s3, a) => s3 + (a.cost || 0), 0), 0), 0));
      const notes = (o.notes || '') + (o.notes && !o.notes.endsWith('\n') ? '\n' : '') + p.text;
      if (DRY) { out.push({ title: p.title, dry: true, cells: n, totalCost: total }); continue; }
      const r = await window.__updOrder(p.id, { items, totalCost: total, notes });
      if (r.err && (Array.isArray(r.err) ? r.err.length : r.err)) { out.push({ title: p.title, error: r.err, unsure: true }); break; }
      const a = await window.__fetchOrder(p.id);
      const after = clean(a.d);
      const same = skel(after) === skel(o);
      const priced = p.cells.every(c => after.items[c.item].variants[c.variant].amounts.every(x => x.price === c.price));
      const sumOk = Math.abs((after.totalCost || 0) - total) <= 0.01;
      const notesOk = (after.notes || '').indexOf('pf:' + p.marker) >= 0;
      const rec = { title: p.title, cells: n, totalCost: after.totalCost, dataUnchanged: same, pricesOk: priced, sumOk, notesOk };
      out.push(rec);
      if (!same || !priced || !sumOk || !notesOk) { rec.ABBRUCH = 'Abweichung nach Update: Backup output/backup/ pruefen'; break; }
    } catch (e) { out.push({ title: p.title, error: String(e && e.message || e).slice(0, 300), unsure: true }); break; }
  }
  return out;
})()
