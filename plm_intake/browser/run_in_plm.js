// Fuehrt ein Browser-Skript (z. B. output/intake/run_*.js) im eingeloggten Lifecycle-Tab aus, ohne dass jemand im Chat klicken muss.
//   node run_in_plm.js <script.js> [--login]      --login: sichtbares Fenster, einmal einloggen (Profil wird gespeichert)
// Profil: ~/.plm_browser_profile (eigenes Chrome-Profil, getrennt vom normalen). Ergebnis: JSON auf stdout und <script>.result.json
const { chromium } = require('playwright-core');
const fs = require('fs'), os = require('os'), path = require('path');
const APP = 'https://app.lifecycleplm.com/';
const HELPERS = path.resolve(__dirname, '../../output/review/chrome_order_helpers.js');

(async () => {
  const args = process.argv.slice(2);
  const login = args.includes('--login');
  const file = args.find(a => !a.startsWith('--'));
  if (!file && !login) { console.error('Aufruf: node run_in_plm.js <script.js> [--login]'); process.exit(2); }
  const ctx = await chromium.launchPersistentContext(path.join(os.homedir(), '.plm_browser_profile'), { channel: 'chrome', headless: !login, viewport: { width: 1400, height: 900 } });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto(APP, { waitUntil: 'domcontentloaded' });
  const ready = () => page.waitForFunction(() => !!window.__APOLLO_CLIENT__ && !/login|sign-?in|auth/i.test(location.pathname), null, { timeout: login ? 600000 : 45000 });
  try { await ready(); } catch (e) {
    await ctx.close();
    console.error(login ? 'Login nicht abgeschlossen.' : 'Nicht eingeloggt. Einmal "node run_in_plm.js --login" ausfuehren und im Fenster einloggen.');
    process.exit(3);
  }
  if (login) { console.log('Eingeloggt, Profil gespeichert.'); await ctx.close(); return; }
  await page.evaluate(fs.readFileSync(HELPERS, 'utf8'));
  const result = await page.evaluate(fs.readFileSync(file, 'utf8'));
  fs.writeFileSync(file.replace(/\.js$/, '') + '.result.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await ctx.close();
})().catch(e => { console.error(String(e && e.stack || e)); process.exit(1); });
