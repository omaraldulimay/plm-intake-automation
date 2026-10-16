// Misst die teuren Operationen eines Laufs im "reifen" Zustand (viele Dateien/Zeilen). Aufruf: node apps_script/test/profile.js
const fs = require('fs'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, 'test_extract.js'), 'utf8');
const head = src.slice(0, src.indexOf("const okDoc"));
const body = `
const okDoc = (e = {}) => ({ doc_type: 'PI', vendor: 'X', po_number: 'P1', currency: 'USD', items: [{ sku: 'S', name: 'n', variants: [{ color: 'Black', price: 1, sizes: { S: 10 } }] }], payments: [], notes: '', open: [], ...e });
const resp = (docs, w, u, events) => ({ code: 200, text: JSON.stringify({ usage: u, stop_reason: 'end_turn', content: [{ type: 'text', text: JSON.stringify({ documents: docs, events }) }] }) });
function scenario(label, mature) {
  const s = fresh({ api: [(n) => resp([okDoc({ po_number: 'P' + n })], null, { input_tokens: 5000, output_tokens: 500 }, [])] });
  const sh = s.ss.getSheetByName('Exportiert'); sh.insertRowsAfter(1000, 60000);
  for (let i = 0; i < 13000; i++) sh.rows.push(['x' + i, new Date(Date.UTC(2026, 0, 1) + i * 3600e3 * 5), 'a@b.c', i % 520 === 0 ? 'PI ' + i : 'Newsletter ' + i, i % 520 === 0 ? 1 : 0, i % 520 === 0 ? 'A' + i + '.pdf' : '', 'mails_1.txt']);
  for (let i = 0; i < 13000; i += 520) s.att.createFile('A' + i + '.pdf', 'inhalt' + i);
  s.root.createFile('mails_1.txt', '');
  if (mature) {   // Inbox mit 2000 Dateien und Review/Ereignisse mit je 2000 Zeilen wie nach Wochen Betrieb
    const inbox = s.root.createFolder('Inbox'); for (let i = 0; i < 2000; i++) inbox.createFile('old' + i + '_1.json', '{}');
    const rv = s.ss.getSheetByName('Review') || s.ss.insertSheet('Review'); rv.appendRow(['Message-ID']); rv.insertRowsAfter(1000, 5000); for (let i = 0; i < 2000; i++) rv.rows.push(['old' + i, '', '', '', '', '', 0, 0, '', '', 'Neu', 'f', '']);
  }
  s.ctx.EX_CONFIG.MAX_CALLS_PER_RUN = 25;
  Object.keys(s.ops).forEach(k => s.ops[k] = 0); const t0 = Date.now(); s.run(); const virt = (Date.now() - t0) / 1000;
  console.log(label.padEnd(34), JSON.stringify(s.ops), 'API-Aufrufe:', s.api.length, '| virtuelle Laufzeit s:', virt.toFixed(0));
}
scenario('frisch', false); scenario('reif (2000 Dateien/Zeilen)', true);
`;
eval(head + body);
