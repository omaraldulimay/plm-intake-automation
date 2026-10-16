// Liest ALLE GraphQL-Operationen (query/mutation/fragment) aus dem JS-Bundle der Lifecycle-App (nur lesen) und schreibt sie als JSON.
//   node dump_gql.js <ausgabe.json>
const { chromium } = require('playwright-core'); const os = require('os'), path = require('path'), fs = require('fs');
(async () => {
  const ctx = await chromium.launchPersistentContext(path.join(os.homedir(), '.plm_browser_profile'), { channel: 'chrome', headless: true });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('https://app.lifecycleplm.com/', { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(9000);
  const ops = await page.evaluate(async () => {
    const urls = [...new Set(performance.getEntriesByType('resource').map(e => e.name).filter(u => /\.js(\?|$)/.test(u)))];
    const out = []; const seen = new Set();
    for (const u of urls) {
      const t = await fetch(u).then(r => r.text()).catch(() => '');
      const re = /`\s*((?:query|mutation|fragment|subscription)\s[^`]{10,12000})`/g; let m;
      while ((m = re.exec(t))) { const s = m[1].replace(/\s+/g, ' ').trim(); if (!seen.has(s)) { seen.add(s); out.push(s); } }
    }
    return out;
  });
  fs.writeFileSync(process.argv[2], JSON.stringify(ops, null, 1)); console.log('Operationen:', ops.length);
  await ctx.close();
})();
