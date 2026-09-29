/* A slow secondary dashboard request must not delay live chat updates. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const origin = new URL(config.url);
  assert.equal(origin.hostname, '127.0.0.1');
  assert(!['8787', '1234', '4315', '4316'].includes(origin.port));
  const results = [];
  for (const engine of ['chromium', 'webkit']) {
    const browser = await playwright[engine].launch({headless: true});
    let release;
    try {
      const context = await browser.newContext({viewport: {width: 390, height: 844}, reducedMotion: 'reduce'});
      await context.route('**/*', route => new URL(route.request().url()).origin === origin.origin ? route.continue() : route.abort());
      const page = await context.newPage(), errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const held = new Promise(resolve => {release = resolve;});
      let requested;
      const overviewStarted = new Promise(resolve => {requested = resolve;});
      await page.route('**/api/overview**', async route => {
        requested(); await held;
        await route.continue().catch(() => {});
      });
      await page.goto(config.url + '/login');
      await page.locator('#password').fill(config.password);
      await page.locator('#login-form button').click();
      await page.waitForURL(config.url + '/');
      await page.locator('#message:enabled').waitFor();
      await overviewStarted;
      const body = engine + ' cold start reminder ' + Date.now();
      const started = Date.now();
      await page.evaluate(async body => {
        const session = await (await fetch('/api/session')).json();
        const response = await fetch('/api/messages', {method: 'POST', headers: {
          'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf},
          body: JSON.stringify({conversation_id: localStorage.getItem('bob.conversation'),
            message: 'remind me to ' + body + ' in 1 second', request_id: crypto.randomUUID()})});
        if (response.status !== 202) throw new Error('Synthetic reminder could not be created');
      }, body);
      // This is a server-created update, not a composer request that can invoke
      // its own reply polling. The normal chat poll must already be running.
      await page.locator('.message.assistant').filter({hasText: 'Reminder: ' + body}).waitFor({timeout: 6000});
      const appearedAfterMs = Date.now() - started;
      assert.equal(await page.locator('#offline-banner').isVisible(), false);
      assert.equal(await page.locator('#message').isEnabled(), true);
      const overview = page.waitForResponse(r => new URL(r.url()).pathname === '/api/overview');
      release();
      assert.equal((await overview).status(), 200);
      for (const width of [320, 390, 430]) {
        await page.setViewportSize({width, height: 844});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      }
      await page.setViewportSize({width: 390, height: 844});
      const screenshot = engine + '-cold-chat.png';
      await page.screenshot({path: path.join(config.output, screenshot), animations: 'disabled'});
      assert.deepEqual(errors, []);
      results.push({engine, passed: true, appearedAfterMs, screenshot,
        checks: ['chat updates while initial overview is stalled', 'no false offline banner', 'composer remains available', 'overview recovers', 'phone layout']});
      await context.close();
    } finally { if (release) release(); await browser.close(); }
  }
  console.log(JSON.stringify({all_pass: true, browsers: results}));
})().catch(error => {console.error(error.stack); process.exitCode = 1;});
