const { chromium } = require('playwright-core'); const os = require('os'), path = require('path');
(async () => {
  const ctx = await chromium.launchPersistentContext(path.join(os.homedir(), '.plm_browser_profile'), { channel: 'chrome', headless: true, viewport: { width: 1600, height: 1000 } });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('https://app.lifecycleplm.com/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  await page.getByText('Products', { exact: true }).first().click({ force: true }).catch(e => console.log('click', e.message.slice(0,80)));
  await page.waitForTimeout(5000);
  console.log(page.url());
  const btns = await page.$$eval('button, [role=button], a', els => els.map(e => (e.getAttribute('aria-label') || e.title || e.innerText || '').trim().slice(0, 40)).filter(Boolean));
  console.log(JSON.stringify([...new Set(btns)].slice(0, 80)));
  await page.screenshot({ path: process.argv[2] });
  await ctx.close();
})();
