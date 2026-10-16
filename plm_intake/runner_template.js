(async () => {
  // Erzeugt von plm_intake/run.py. Legt die POs nacheinander an und BRICHT beim ersten Fehler ab (kein automatisches Wiederholen:
  // nach einem unsicheren Ergebnis zuerst per REST pruefen, ob die Order existiert).
  const PAYLOADS = __PAYLOADS__;
  const DRY = __DRY__;
  const out = [];
  if (!DRY && (typeof window.__createOrder !== 'function')) return [{ fatal: 'Helfer nicht geladen (chrome_order_helpers.js zuerst ausfuehren)' }];
  const seen = new Set();
  for (const p of PAYLOADS) {
    const t = p.title;
    if (seen.has(t)) { out.push({ title: t, skipped: 'doppelt im Lauf' }); continue; }
    seen.add(t);
    if (DRY) { out.push({ title: t, dry: true, items: p.items.length, totalCost: p.totalCost, pieces: p.totalNumberOfPieces }); continue; }
    try {
      const r = await window.__createOrder(p);
      const c = r && r.data && r.data.createOrder;
      if ((r && r.errors && r.errors.length) || !c) {
        // "Order with id X was not found" kommt oft, obwohl die PO gespeichert wurde (Lesen direkt nach Schreiben). Id aus der Meldung nehmen und kurz nachlesen.
        const m = /Order with id (\w{24}) was not found/.exec(JSON.stringify((r && r.errors) || ''));
        let ok = null;
        if (m) for (let i = 0; i < 6 && !ok; i++) { await new Promise(res => setTimeout(res, 3000)); const f = await window.__fetchOrder(m[1]); if (f && f.d && f.d.title === t) ok = f.d; }
        if (ok) { out.push({ title: t, id: ok.id, orderNumber: 'nachgelesen', totalCost: ok.totalCost, pieces: ok.totalNumberOfPieces, note: 'Antwort war Fehler, PO per Nachlesen bestaetigt' }); continue; }
        out.push({ title: t, error: (r && r.errors) || 'keine Antwort', unsure: true }); break;
      }
      out.push({ title: t, orderNumber: c.orderNumber, totalCost: c.totalCost, pieces: c.totalNumberOfPieces });
    } catch (e) {
      out.push({ title: t, error: String(e && e.message || e).slice(0, 300), unsure: true });
      break;
    }
  }
  return out;
})()
