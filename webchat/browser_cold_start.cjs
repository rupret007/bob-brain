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
      await context.addInitScript(() => {
        const timeout = AbortSignal.timeout.bind(AbortSignal);
        AbortSignal.timeout = ms => {
          if (window.__shortPostTimeout && ms === 45000) {
            window.__postTimeoutRequested = ms;
            return timeout(250);
          }
          return timeout(ms);
        };
      });
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
      async function submit(message) {
        return page.evaluate(async message => {
          const session = await (await fetch('/api/session')).json();
          const response = await fetch('/api/messages', {method: 'POST', headers: {
            'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf},
            body: JSON.stringify({conversation_id: localStorage.getItem('bob.conversation'),
              message, request_id: crypto.randomUUID()})});
          if (response.status !== 202) throw new Error('Synthetic reminder could not be created');
          return response.json();
        }, message);
      }
      async function reminderCount(body) {
        return page.evaluate(async body => {
          const data = await (await fetch('/api/reminders')).json();
          return data.reminders.filter(row => row.body === body).length;
        }, body);
      }
      function confirmation(value) {
        const content = value.messages.at(-1).content;
        const match = content.match(/Reply `(yes wbrem-[0-9a-f]{32})`/);
        assert(match, content);
        return match[1];
      }
      const body = engine + ' cold start reminder ' + Date.now();
      const started = Date.now();
      // Exercise the draft path; explicit personal intervals save directly.
      const initialDraft = await submit('create a reminder to ' + body + ' in 1 second');
      assert.equal(await reminderCount(body), 0, 'A reminder draft must not schedule a notification');
      await submit(confirmation(initialDraft));
      // This is a server-created update, not a composer request that can invoke
      // its own reply polling. The normal chat poll must already be running.
      await page.locator('.message.assistant').filter({hasText: 'Reminder: ' + body}).waitFor({timeout: 6000});
      const dueNotice = page.locator('.message.assistant .body').filter({
        hasText: new RegExp('^Reminder: ' + body + ' \\(due [^)]+\\)\\.$')});
      await dueNotice.waitFor({timeout: 6000});
      assert.equal(await dueNotice.count(), 1, 'The live update must be a real due notification');
      const appearedAfterMs = Date.now() - started;
      assert.equal(await page.locator('#offline-banner').isVisible(), false);
      assert.equal(await page.locator('#message').isEnabled(), true);
      const overview = page.waitForResponse(r => new URL(r.url()).pathname === '/api/overview');
      release();
      assert.equal((await overview).status(), 200);
      // Draft first, then hold the exact confirmation's HTTP acknowledgment.
      // The UI must regain control without replaying the accepted mutation.
      const pendingBody = engine + ' recovery reminder ' + Date.now();
      const pendingRequest = 'create a reminder to ' + pendingBody + ' in 10 minutes';
      const pendingDraft = await submit(pendingRequest);
      assert.equal(await reminderCount(pendingBody), 0, 'The pending reminder needs separate consent');
      const pendingText = confirmation(pendingDraft);
      const requests = [];
      let releasePost;
      const postHeld = new Promise(resolve => { releasePost = resolve; });
      const intercept = async route => {
        requests.push(route.request().postDataJSON());
        if (requests.length !== 1) return route.continue();
        const response = await route.fetch();
        await postHeld;
        await route.fulfill({response}).catch(() => {});
      };
      await page.route('**/api/messages', intercept);
      const timeoutScreenshot = engine + '-post-timeout.png';
      try {
        await page.evaluate(() => { window.__shortPostTimeout = true; });
        await page.locator('#message').fill(pendingText);
        await page.locator('#send:enabled').click();
        await page.locator('#notice').filter({hasText: 'Request timed out.'}).waitFor({timeout: 3000});
        assert.equal(await page.evaluate(() => window.__postTimeoutRequested), 45000);
        assert.equal(await page.locator('#message').inputValue(), pendingText);
        assert.equal(await page.locator('#send').isEnabled(), true);
        assert.equal(requests.length, 1, 'The UI must not automatically retry a mutation');
        await page.screenshot({path: path.join(config.output, timeoutScreenshot), animations: 'disabled'});
        releasePost();
        await page.evaluate(() => { window.__shortPostTimeout = false; });
        const retried = page.waitForResponse(r => new URL(r.url()).pathname === '/api/messages' && r.request().method() === 'POST');
        await page.locator('#send:enabled').click();
        const recovered = await (await retried).json();
        assert.equal(requests.length, 2);
        assert.deepEqual(requests[1], requests[0], 'A manual retry must retain the exact request identity');
        assert.equal(recovered.messages.filter(m => m.role === 'user' && m.request_id === requests[0].request_id).length, 1);
        const count = await page.evaluate(async body => {
          const data = await (await fetch('/api/reminders')).json();
          return data.reminders.filter(row => row.body === body).length;
        }, pendingBody);
        assert.equal(count, 1, 'The accepted reminder must not be created twice');
      } finally {
        releasePost();
        await page.unroute('**/api/messages', intercept);
        await page.evaluate(() => { window.__shortPostTimeout = false; });
      }
      for (const width of [320, 390, 430]) {
        await page.setViewportSize({width, height: 844});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      }
      await page.setViewportSize({width: 390, height: 844});
      const screenshot = engine + '-cold-chat.png';
      await page.screenshot({path: path.join(config.output, screenshot), animations: 'disabled'});
      assert.deepEqual(errors, []);
      results.push({engine, passed: true, appearedAfterMs, screenshot, timeoutScreenshot,
        checks: ['chat updates while initial overview is stalled', 'no false offline banner', 'composer remains available', 'overview recovers', 'bounded POST wait and honest uncertainty', 'manual retry retains identity with one accepted reminder', 'phone layout']});
      await context.close();
    } finally { if (release) release(); await browser.close(); }
  }
  console.log(JSON.stringify({all_pass: true, browsers: results}));
})().catch(error => {console.error(error.stack); process.exitCode = 1;});
