const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const origin = new URL(config.url);
  assert.equal(origin.hostname, '127.0.0.1');
  assert(!['8787', '1234', '4315', '4316'].includes(origin.port));
  const browsers = [];
  for (const engine of ['chromium', 'webkit']) {
    const browser = await playwright[engine].launch({headless: true});
    const cases = [];
    try {
      for (const target of ['session', 'list', 'history', 'timeout']) {
        const context = await browser.newContext({viewport: {width: 320, height: 844}, reducedMotion: 'reduce'});
        if (target === 'timeout') await context.addInitScript(() => {
          const timeout = AbortSignal.timeout.bind(AbortSignal);
          AbortSignal.timeout = ms => {
            if (!window.__startupReadDeadline && ms === 15000) {
              window.__startupReadDeadline = ms;
              return timeout(250);
            }
            return timeout(ms);
          };
        });
        await context.route('**/*', route => new URL(route.request().url()).origin === origin.origin ? route.continue() : route.abort());
        const page = await context.newPage(), errors = [], mutations = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('request', request => {
          if (request.method() !== 'GET' && new URL(request.url()).pathname.startsWith('/api/')) mutations.push(request.url());
        });
        const calls = {session: 0, list: 0, history: 0};
        let failedAt = 0, retriedAt = 0, releaseRead;
        const held = new Promise(resolve => { releaseRead = resolve; });
        const targetKind = target === 'timeout' ? 'session' : target;
        await page.route('**/api/**', async route => {
          const pathname = new URL(route.request().url()).pathname;
          const kind = pathname === '/api/session' ? 'session' : pathname === '/api/conversations' ? 'list'
            : pathname.startsWith('/api/conversations/') ? 'history' : '';
          if (kind) calls[kind]++;
          if (kind === targetKind && calls[kind] === 1) {
            failedAt = Date.now();
            if (target === 'timeout') {
              await held;
              return route.continue().catch(() => {});
            }
            if (target === 'list') return route.abort('failed');
            return route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: 'Temporary fixture outage'})});
          }
          if (kind === targetKind && calls[kind] === 2) retriedAt = Date.now();
          return route.continue();
        });
        await page.goto(config.url + '/login');
        await page.locator('#password').fill(config.password);
        await page.locator('#login-form button').click();
        await page.waitForURL(config.url + '/');
        // A failed first read must recover without a reload or mutation replay.
        try {
          await page.locator('#offline-banner:visible').waitFor({timeout: 3000});
        } catch (error) {
          await page.screenshot({path: path.join(config.output, `${engine}-${target}-failed.png`), animations: 'disabled'});
          await page.locator('#message:enabled').waitFor({timeout: 9000});
          throw error;
        }
        assert.equal(await page.locator('#message').isEnabled(), false);
        assert.equal(await page.locator('#new-chat').isEnabled(), false);
        // Even programmatic interaction cannot submit work before readiness.
        await page.locator('#composer').dispatchEvent('submit');
        await page.locator('#manage-memory').dispatchEvent('click');
        await page.locator('#new-chat').dispatchEvent('click');
        await page.locator('#message:enabled').waitFor({timeout: 9000});
        await page.locator('#offline-banner').waitFor({state: 'hidden'});
        releaseRead();
        if (target === 'timeout') assert.equal(await page.evaluate(() => window.__startupReadDeadline), 15000);
        assert(retriedAt - failedAt >= 4800 && retriedAt - failedAt < 8500, 'Bounded startup backoff');
        await page.locator('#message').fill('Unsent private fixture draft <literal>');
        // Reconnect signals after readiness must use normal polling, not repeat
        // initialization, lose a draft, or attach more recurring timers.
        const sessionCalls = calls.session;
        const historyCalls = calls.history;
        await page.evaluate(() => { window.dispatchEvent(new Event('online')); document.dispatchEvent(new Event('visibilitychange')); });
        await page.waitForTimeout(2800);
        assert.equal(calls.session, sessionCalls);
        assert(calls.history >= historyCalls + 2 && calls.history <= historyCalls + 4);
        assert.equal(await page.locator('#message').inputValue(), 'Unsent private fixture draft <literal>');
        for (const width of [320, 390, 430]) {
          await page.setViewportSize({width, height: 844});
          await page.waitForTimeout(200);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
        }
        const screenshot = `${engine}-${target}-recovered.png`;
        await page.screenshot({path: path.join(config.output, screenshot), animations: 'disabled'});
        assert.deepEqual(errors, []);
        assert.deepEqual(mutations, []);
        cases.push({target, passed: true, retryAfterMs: retriedAt - failedAt, calls, screenshot});
        await context.close();
      }
      const context = await browser.newContext();
      const page = await context.newPage();
      let unauthorizedReads = 0;
      await context.route('**/*', route => new URL(route.request().url()).origin === origin.origin ? route.continue() : route.abort());
      await page.route('**/api/session', route => {
        unauthorizedReads++;
        return route.fulfill({status: 401, contentType: 'application/json', body: '{"error":"Please log in."}'});
      });
      await page.goto(config.url + '/login');
      await page.locator('#password').fill(config.password);
      const denied = page.waitForResponse(response => new URL(response.url()).pathname === '/api/session' && response.status() === 401);
      await page.locator('#login-form button').click();
      await denied;
      await page.waitForURL(config.url + '/login');
      await page.locator('#password').waitFor();
      await page.evaluate(() => window.dispatchEvent(new Event('online')));
      await page.waitForTimeout(1400);
      assert.equal(unauthorizedReads, 1);
      cases.push({target: 'unauthorized', passed: true, unauthorizedReads});
      await context.close();
      browsers.push({engine, passed: true, cases});
    } finally { await browser.close(); }
  }
  console.log(JSON.stringify({all_pass: true, browsers}));
})().catch(error => {console.error(error.stack); process.exitCode = 1;});
