// Fuehrt ein Browser-Skript (z. B. output/intake/run_*.js) im eingeloggten Lifecycle-Tab aus, ohne dass jemand im Chat klicken muss.
//   node run_in_plm.js <script.js> [--login]      --login: sichtbares Fenster, einmal einloggen (Profil wird gespeichert)
// Profil: ~/.plm_browser_profile (eigenes Chrome-Profil, getrennt vom normalen). Ergebnis: JSON auf stdout und <script>.result.json
const { chromium } = require('playwright-core');
const fs = require('fs'), os = require('os'), path = require('path');
const APP = 'https://app.lifecycleplm.com/';
const HELPERS = [path.resolve(__dirname, 'chrome_order_helpers.js'), path.resolve(__dirname, '../../output/review/chrome_order_helpers.js')].find(f => fs.existsSync(f));
// Cloud-Modus (env CI gesetzt, z. B. GitHub Actions): headless Chromium von Playwright, Login mit PLM_EMAIL/PLM_PASSWORD (Formular app.lifecycleplm.com/login:
// input[name=email], input[name=password], Button SIGN IN). Die Sitzung wird je Lauf in PLM_STORAGE_STATE (Datei im Runner-Temp, nie im Repo) zwischengespeichert,
// damit die vielen Aufrufe eines Laufs nur einmal einloggen. Lokal (ohne CI) bleibt alles wie vorher: Chrome mit persistentem Profil.
const CLOUD = !!process.env.CI;
const STATE = process.env.PLM_STORAGE_STATE || path.join(os.tmpdir(), 'plm_storage_state.json');

async function cloudLogin(page) {
  const email = process.env.PLM_EMAIL, pw = process.env.PLM_PASSWORD;
  if (!email || !pw) throw new Error('PLM_EMAIL/PLM_PASSWORD fehlen (GitHub Secrets)');
  await page.goto(APP + 'login', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('input[name=email]', { timeout: 30000 });
  await page.fill('input[name=email]', email);
  await page.fill('input[name=password]', pw);
  await page.click('button[type=submit]');
}

(async () => {
  const args = process.argv.slice(2);
  const login = args.includes('--login');
  const file = args.find(a => !a.startsWith('--'));
  if (!file && !login) { console.error('Aufruf: node run_in_plm.js <script.js> [--login]'); process.exit(2); }
  let ctx, browser = null;
  if (CLOUD) {
    browser = await chromium.launch({ headless: true, ...(process.env.PLM_CLOUD_CHANNEL ? { channel: process.env.PLM_CLOUD_CHANNEL } : {}) });   // PLM_CLOUD_CHANNEL=chrome nur fuer lokalen Test
    ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, ...(fs.existsSync(STATE) ? { storageState: STATE } : {}) });
  } else {
    ctx = await chromium.launchPersistentContext(path.join(os.homedir(), '.plm_browser_profile'), { channel: 'chrome', headless: !login, viewport: { width: 1400, height: 900 } });
  }
  const closeAll = async () => { await ctx.close(); if (browser) await browser.close(); };
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto(APP, { waitUntil: 'domcontentloaded' });
  const ready = (t) => page.waitForFunction(() => !!window.__APOLLO_CLIENT__ && !/login|sign-?in|auth/i.test(location.pathname), null, { timeout: t || (login ? 600000 : 45000) });
  try {
    if (CLOUD) {
      // Frische Sitzung: "/" ist kurz erreichbar, bevor die App auf /login umleitet -> nach dem Warten nochmals pruefen (Pfad + kein Passwortfeld).
      const settled = async (t) => { await ready(t); await page.waitForTimeout(3000); return page.evaluate(() => !/login|sign-?in|auth/i.test(location.pathname) && !document.querySelector('input[type=password]')); };
      let ok = false;
      try { ok = await settled(15000); } catch (e) { ok = false; }
      if (!ok) { await cloudLogin(page); if (!(await settled(60000))) throw new Error('Login abgelehnt (Zugangsdaten/2FA pruefen)'); }
      try { await ctx.storageState({ path: STATE }); } catch (e) { /* Zwischenspeicher ist optional */ }
    } else {
      await ready();
    }
  } catch (e) {
    if (CLOUD) { try { await page.screenshot({ path: path.join(process.env.PLM_DEBUG_DIR || os.tmpdir(), 'plm_login_fehler.png') }); } catch (_) {} console.error('Cloud-Login gescheitert: ' + String(e && e.message || e).split('\n')[0]); }
    await closeAll();
    console.error(CLOUD ? 'Nicht eingeloggt (Cloud-Login, siehe oben; PLM_EMAIL/PLM_PASSWORD und 2FA pruefen).' : login ? 'Login nicht abgeschlossen.' : 'Nicht eingeloggt. Einmal "node run_in_plm.js --login" ausfuehren und im Fenster einloggen.');
    process.exit(3);
  }
  if (login) { console.log('Eingeloggt, Profil gespeichert.'); await closeAll(); return; }
  await page.evaluate(fs.readFileSync(HELPERS, 'utf8'));
  const result = await page.evaluate(fs.readFileSync(file, 'utf8'));
  fs.writeFileSync(file.replace(/\.js$/, '') + '.result.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await closeAll();
})().catch(e => { console.error(String(e && e.stack || e)); process.exit(1); });
