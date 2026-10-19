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
console.log(res.join('\n')); if (res.some(l => l.startsWith('FEHL'))) process.exit(1);
