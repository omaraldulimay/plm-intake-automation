// CSV-Produktimport in Lifecycle per Browser.   node import_csv.js <datei.csv> [--commit] [--update] [--shots <ordner>]
// Ohne --commit nur bis zur Vorschau (nichts wird gespeichert). Ergebnis (Vorschau-Text bzw. Meldung) auf stdout.
const { chromium } = require('playwright-core'); const os = require('os'), path = require('path'), fs = require('fs');
(async () => {
  const a = process.argv.slice(2); const file = a.find(x => !x.startsWith('--') && x.endsWith('.csv'));
  const commit = a.includes('--commit'), update = a.includes('--update'); const si = a.indexOf('--shots'); const shots = si >= 0 ? a[si + 1] : null;
  if (!file) { console.error('Aufruf: node import_csv.js <datei.csv> [--commit] [--update] [--shots <ordner>]'); process.exit(2); }
  const shot = async (p, n) => { if (shots) await p.screenshot({ path: path.join(shots, n + '.png') }); };
  const ctx = await chromium.launchPersistentContext(path.join(os.homedir(), '.plm_browser_profile'), { channel: 'chrome', headless: true, viewport: { width: 1600, height: 1000 } });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('https://app.lifecycleplm.com/', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!window.__APOLLO_CLIENT__, null, { timeout: 45000 });
  await page.goto('https://app.lifecycleplm.com/collections', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000); await shot(page, '0-liste');
  const importBtn = page.locator('button[aria-label="Import CSV"]');   // Seite laedt manchmal >5 s; Knopf per Beschriftung statt Pixelposition
  await importBtn.waitFor({ state: 'visible', timeout: 60000 });
  await importBtn.click();
  await page.waitForTimeout(1500); await shot(page, '1-dialog');
  await page.locator('input[type=file]').first().setInputFiles(path.resolve(file), { timeout: 60000 });
  await page.waitForTimeout(2500); await shot(page, '1b-nach-upload');
  if (update) { const cb = page.getByText(/Update existing products/i).first(); if (await cb.count()) await cb.click({ force: true }); }
  await page.getByRole('button', { name: /^review$/i }).click({ timeout: 15000 });
  await page.waitForTimeout(4000); await shot(page, '2-vorschau');
  const text = async () => (await page.evaluate(() => document.body.innerText)).replace(/\n{2,}/g, '\n').slice(0, 1800);
  console.log('VORSCHAU:\n' + await text());
  if (commit) {
    const btn = page.getByRole('button', { name: /^import( \d+)?/i }).last();
    console.log('KLICK:', (await btn.innerText()).trim());
    await btn.click({ timeout: 15000 });
    await page.waitForTimeout(25000); await shot(page, '3-ergebnis');
    console.log('ERGEBNIS:\n' + await text());
  }
  await ctx.close();
})().catch(e => { console.error(String(e && e.stack || e)); process.exit(1); });
