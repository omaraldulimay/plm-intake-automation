// Test fuer den Waechter in extract_po.gs (reine Entscheidungsfunktion). Aufruf: node apps_script/test/test_watchdog.js
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const ctx = { Logger: { log() {} }, console, Date, JSON, Math, Number, isNaN, parseInt, RegExp, Object, Array, String };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(__dirname + '/../extract_po.gs', 'utf8'), ctx);
const T = (s) => Date.parse(s), d = ctx.exWatchdogDecision_;
const res = []; const t = (n, f) => { try { f(); res.push('OK   ' + n); } catch (e) { res.push('FEHL ' + n + ' | ' + e.message); } };
const hb = (iso, o = {}) => Object.assign({ last_run: iso, state: 'OK', mode: 'apply' }, o);
t('frischer Lauf, Dienstag: keine Warnung', () => assert.strictEqual(d(T('2026-10-20T10:00:00+02:00'), hb('2026-10-19T19:45:00+02:00'), 2), null));
t('Dienstag, letzter Lauf vor 40 h: Warnung', () => assert.ok(d(T('2026-10-20T10:00:00+02:00'), hb('2026-10-18T18:00:00+02:00'), 2)));
t('Montag nach Wochenende (62 h): noch ok', () => assert.strictEqual(d(T('2026-10-19T10:00:00+02:00'), hb('2026-10-16T19:45:00+02:00'), 1), null));
t('Montag, letzter Lauf vor 5 Tagen: Warnung', () => assert.ok(d(T('2026-10-19T10:00:00+02:00'), hb('2026-10-15T12:14:16+02:00'), 1)));
t('Samstag/Sonntag nie', () => { assert.strictEqual(d(T('2026-10-24T10:00:00+02:00'), null, 6), null); assert.strictEqual(d(T('2026-10-25T10:00:00+02:00'), null, 7), null); });
t('keine Datei: Warnung', () => assert.ok(/keinen Herzschlag/.test(d(T('2026-10-20T10:00:00+02:00'), null, 2))));
t('state ALARM: Warnung', () => assert.ok(/Problem/.test(d(T('2026-10-20T10:00:00+02:00'), hb('2026-10-19T19:45:00+02:00', { state: 'ALARM', text: 'Login' }), 2))));
t('Trockenmodus: Warnung', () => assert.ok(/Trockenmodus/.test(d(T('2026-10-20T10:00:00+02:00'), hb('2026-10-19T19:45:00+02:00', { mode: 'dry' }), 2))));
t('unlesbares Datum: Warnung', () => assert.ok(d(T('2026-10-20T10:00:00+02:00'), { last_run: 'unlesbar' }, 2)));
// ---- Cloud-Waechter (GitHub Actions)
const cw = ctx.exCloudWatchdogDecision_;
const run = (created, secs, concl = 'success', st = 'completed') => ({ created_at: created, run_started_at: created, updated_at: new Date(Date.parse(created) + secs * 1000).toISOString(), conclusion: concl, status: st, html_url: 'https://github.com/x/y/actions/runs/1' });
t('Cloud: echter Lauf (9 Min) heute morgen: keine Warnung', () => assert.strictEqual(cw(T('2026-10-21T08:30:00Z'), [run('2026-10-21T06:00:05Z', 540)], 3, 5), null));
t('Cloud: nur uebersprungener Lauf (10 s): Warnung', () => assert.ok(/Zeitfenster uebersprungen/.test(cw(T('2026-10-20T14:00:00Z'), [run('2026-10-20T12:30:04Z', 10)], 2, 11))));
t('Cloud: gar kein Lauf: Warnung "nicht ausgeloest"', () => assert.ok(/nicht ausgeloest/.test(cw(T('2026-10-20T14:00:00Z'), [run('2026-10-20T08:06:29Z', 540)], 2, 11))));   // der Morgenlauf zaehlt nicht fuer mittags
t('Cloud: fehlgeschlagener Lauf: Warnung mit Link', () => assert.ok(/fehlgeschlagen.*github\.com/s.test(cw(T('2026-10-21T08:30:00Z'), [run('2026-10-21T06:00:05Z', 300, 'failure')], 3, 5))));
t('Cloud: Lauf laeuft noch: keine Warnung', () => assert.strictEqual(cw(T('2026-10-21T08:30:00Z'), [run('2026-10-21T08:25:00Z', 30, null, 'in_progress')], 3, 5), null));
t('Cloud: Wochenende nie', () => { assert.strictEqual(cw(T('2026-10-24T08:30:00Z'), [], 6, 5), null); assert.strictEqual(cw(T('2026-10-25T08:30:00Z'), [], 7, 5), null); });
t('Cloud: Lauf von gestern zaehlt nicht fuer heute', () => assert.ok(cw(T('2026-10-21T08:30:00Z'), [run('2026-10-20T12:00:00Z', 540)], 3, 5)));
t('Cloud: Handlauf (dispatch) zaehlt wie geplanter Lauf', () => assert.strictEqual(cw(T('2026-10-21T13:00:00Z'), [Object.assign(run('2026-10-21T11:40:00Z', 500), { event: 'workflow_dispatch' })], 3, 11), null));
console.log(res.join('\n')); if (res.some(l => l.startsWith('FEHL'))) process.exit(1);
