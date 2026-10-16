const { chromium } = require('playwright-core'); const os = require('os'), path = require('path');
(async () => {
  const [url, pat] = process.argv.slice(2);
  const ctx = await chromium.launchPersistentContext(path.join(os.homedir(), '.plm_browser_profile'), { channel: 'chrome', headless: true });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(9000);
  const out = await page.evaluate(async (pat) => {
    const urls = [...new Set(performance.getEntriesByType('resource').map(e => e.name).filter(u => /\.js(\?|$)/.test(u)))];
    const hits = [];
    for (const u of urls) { const t = await fetch(u).then(r => r.text()).catch(() => ''); const re = new RegExp(pat, 'g'); let m;
      while ((m = re.exec(t)) && hits.length < 6) hits.push(t.slice(Math.max(0, m.index - 80), m.index + 420).replace(/\s+/g, ' ')); }
    return { n: urls.length, hits };
  }, pat);
  console.log(JSON.stringify(out, null, 1)); await ctx.close();
})();
