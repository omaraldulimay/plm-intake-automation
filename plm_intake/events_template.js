(async () => {
  // Erzeugt von plm_intake/events.py. Haengt Verlaufszeilen an die Notes an, setzt Termine/Zahlungsstatus nur bei eindeutiger Lage.
  // Wiederholbar (Marker ev:<hash>), loescht nie etwas, prueft nach jedem Update: Positionen, Mengen, Preise, Summen, Zahlungsbetraege/-termine unveraendert.
  // Bricht beim ersten Fehler oder jeder Abweichung ab. Voraussetzung: chrome_order_helpers.js geladen.
  const PLAN = __PLAN__;
  const out = [];
  if (typeof window.__fetchOrder !== 'function' || typeof window.__updOrder !== 'function') return [{ fatal: 'Helfer nicht geladen (chrome_order_helpers.js zuerst)' }];
  const clean = a => JSON.parse(JSON.stringify(a, (k, v) => (k === '__typename' ? undefined : v)));
  const core = (o, skipPayIdx) => JSON.stringify({
    t: o.title, c: o.totalCost, n: o.totalNumberOfPieces, m: o.manufacturer && o.manufacturer.id,
    items: (o.items || []).map(i => ({ n: i.name, p: i.product && i.product.id || null, v: (i.variants || []).map(v => ({ n: v.name, id: v.variantId || null, a: (v.amounts || []).map(a => [a.key, a.quantity, a.price, a.cost]) })) })),
    pay: (o.payments || []).map((p, i) => [p.name, i === skipPayIdx ? null : p.status, p.amount, p.dueDate]) });
  const ms = x => (x === null || x === undefined || x === '') ? null : (typeof x === 'number' ? x : /^\d+$/.test(String(x)) ? Number(x) : Date.parse(x));   // PLM liefert Datum teils als ms-Zahl in Textform
  for (const p of PLAN) {
    try {
      const b = await window.__fetchOrder(p.id);
      if (!b.d) { out.push({ title: p.title, error: 'nicht lesbar' }); break; }
      const o = clean(b.d);
      let notes = o.notes || '';
      const lastSched = (notes.match(/\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) ev:[0-9a-f]{8}\] SCHEDULE/g) || []).map(x => x.slice(1, 17)).sort().pop() || '';
      const added = [];
      for (const l of p.lines) if (notes.indexOf('ev:' + l.marker) < 0) { notes += (notes && !notes.endsWith('\n') ? '\n' : '') + l.text; added.push(l.marker); }
      const patch = {};
      if (added.length) patch.notes = notes;
      // Termine: nur wenn die Mail nicht aelter ist als der zuletzt eingetragene SCHEDULE-Eintrag und das Datum sich wirklich aendert
      const dateChanges = {};
      if (p.date_patch && Object.keys(p.date_patch).length && (!lastSched || p.date_mail >= lastSched)) {
        for (const k of Object.keys(p.date_patch)) if (ms(o[k]) !== ms(p.date_patch[k])) dateChanges[k] = p.date_patch[k];
      }
      Object.assign(patch, dateChanges);
      // Zahlungen: nur wenn genau EINE offene Zahlung den Betrag trifft
      const pays = clean(o.payments || []);
      let payIdx = -1;
      const payDone = [];
      for (const z of (p.pay || [])) {
        const c = pays.map((x, i) => [x, i]).filter(([x]) => x.status === 'Unpaid' && Math.abs((x.amount || 0) - z.amount) <= 0.01);
        if (c.length === 1) { pays[c[0][1]].status = 'Paid'; payIdx = c[0][1]; payDone.push(z.amount); }
      }
      if (payDone.length) patch.payments = pays;
      // Status: nur VORWAERTS, nie ab "Complete", nur wenn die Order-Nr der Zielstufe groesser ist als die aktuelle (Prozess: Draft < Approved < In Production < QC < In Transit)
      let statusSet = null;
      if (p.status && p.status.to) {
        const cur = o.status || {};
        if (cur.status !== 'Complete' && (cur.order || 0) < p.status.to.order) { patch.status = p.status.to; statusSet = p.status.to.status; }
      }
      if (!Object.keys(patch).length) { out.push({ title: p.title, unchanged: true }); continue; }
      const r = await window.__updOrder(p.id, patch);
      if (r.err && (Array.isArray(r.err) ? r.err.length : r.err)) { out.push({ title: p.title, error: r.err, unsure: true }); break; }
      const a = await window.__fetchOrder(p.id);
      const after = clean(a.d);
      const skip = payDone.length === 1 ? payIdx : (payDone.length ? -2 : -1);
      const same = payDone.length > 1 ? core({ ...after, payments: [] }) === core({ ...o, payments: [] }) : core(after, skip) === core(o, skip);
      const notesOk = p.lines.every(l => (after.notes || '').indexOf('ev:' + l.marker) >= 0);
      const datesOk = Object.keys(dateChanges).every(k => ms(after[k]) === ms(dateChanges[k]));
      const statusOk = !statusSet || (after.status && after.status.status === statusSet);
      const rec = { title: p.title, statusSet, statusOk, notesAdded: added.length, dates: Object.keys(dateChanges), paymentsMarkedPaid: payDone.length, dataUnchanged: same, notesOk, datesOk };
      out.push(rec);
      if (!same || !notesOk || !datesOk || !statusOk) { rec.ABBRUCH = 'Abweichung nach Update: Backup output/backup/ pruefen'; break; }
      // Sichtbarkeit: neu geschriebene Notizzeilen zusaetzlich als Kommentar in "Chats & Updates" der Bestellung (nur die NEUEN Zeilen, daher ohne Dubletten; Fehler hier aendern keine Daten)
      if (added.length) {
        try {
          const txt = p.lines.filter(l => added.indexOf(l.marker) >= 0).map(l => l.text).join('\n');
          const r2 = await window.__postOrderComment(p.id, txt);
          rec.chat = r2.ok ? added.length : 0;
          if (!r2.ok) rec.chatError = r2.err;
        } catch (e) { rec.chat = 0; rec.chatError = String(e && e.message || e).slice(0, 200); }
      }
    } catch (e) { out.push({ title: p.title, error: String(e && e.message || e).slice(0, 300), unsure: true }); break; }
  }
  return out;
})()
