(async () => {
  // Erzeugt von plm_intake/relink.py. Setzt NUR product/variantId, prueft danach Mengen/Preise/Zahlungen/Summen unveraendert.
  // Voraussetzung: chrome_order_helpers.js geladen (__fetchOrder, __updOrder). Bricht beim ersten Fehler oder jeder Abweichung ab.
  const PLAN = __PLAN__;
  const out = [];
  if (typeof window.__fetchOrder !== 'function' || typeof window.__updOrder !== 'function') return [{ fatal: 'Helfer nicht geladen (chrome_order_helpers.js zuerst)' }];
  const clean = a => JSON.parse(JSON.stringify(a, (k, v) => (k === '__typename' ? undefined : v)));
  const core = o => JSON.stringify({
    t: o.title, c: o.totalCost, n: o.totalNumberOfPieces, m: o.manufacturer && o.manufacturer.id,
    items: (o.items || []).map(i => ({ n: i.name, v: (i.variants || []).map(v => ({ n: v.name, a: (v.amounts || []).map(a => [a.key, a.quantity, a.price, a.cost]) })) })),
    pay: (o.payments || []).map(p => [p.name, p.status, p.amount, p.dueDate]) });
  const links = o => (o.items || []).map(i => [i.product && i.product.id || null, (i.variants || []).map(v => v.variantId || null)]);
  for (const p of PLAN) {
    try {
      const before = await window.__fetchOrder(p.id);
      if (!before.d) { out.push({ title: p.title, error: 'nicht lesbar', unsure: false }); break; }
      const o = clean(before.d);
      const items = o.items.map((it, idx) => {
        const l = p.links.find(x => x.index === idx);
        if (!l) return { ...it, product: it.product ? it.product.id : undefined };
        if (it.name !== l.name) throw new Error('Position ' + idx + ' hat sich geaendert (' + it.name + ' != ' + l.name + ')');
        if (it.product) throw new Error('Position ' + idx + ' ist inzwischen verknuepft');
        return { ...it, product: l.product, variants: it.variants.map(v => ({ ...v, variantId: l.variants[v.name] || v.variantId })) };
      });
      const r = await window.__updOrder(p.id, { items });
      if (r.err && (Array.isArray(r.err) ? r.err.length : r.err)) { out.push({ title: p.title, error: r.err, unsure: true }); break; }
      const after = await window.__fetchOrder(p.id);
      const same = core(clean(after.d)) === core(o);
      const linked = links(clean(after.d));
      const expectLinked = p.links.every(l => linked[l.index][0] === l.product && linked[l.index][1].every(x => x));
      const othersKept = JSON.stringify(links(o).map((x, i) => p.links.some(l => l.index === i) ? null : x)) === JSON.stringify(links(clean(after.d)).map((x, i) => p.links.some(l => l.index === i) ? null : x));
      out.push({ title: p.title, linked: p.links.length, dataUnchanged: same, linksOk: expectLinked, otherLinksKept: othersKept });
      if (!same || !expectLinked || !othersKept) { out[out.length - 1].ABBRUCH = 'Abweichung nach Update: Backup output/backup/ pruefen'; break; }
    } catch (e) { out.push({ title: p.title, error: String(e && e.message || e).slice(0, 300), unsure: true }); break; }
  }
  return out;
})()
