/* Private HTTP fixtures exercise result switching, dismissal and read-only retry. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
async function until(page, predicate) {
  // Poll without eval so the production Content Security Policy stays enabled.
  const deadline = Date.now() + 5000;
  while (!(await page.evaluate(predicate))) {
    assert(Date.now() < deadline, 'Jobs result did not reach the required state');
    await page.waitForTimeout(50);
  }
}
(async () => {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const origin = new URL(config.url);
  assert.equal(origin.hostname, '127.0.0.1');
  assert(!['8787', '1234', '4315', '4316'].includes(origin.port));
  const results = [];
  for (const engine of ['chromium', 'webkit']) {
    const browser = await playwright[engine].launch({headless: true});
    let page, release;
    try {
      const context = await browser.newContext({viewport: {width: 390, height: 844}, reducedMotion: 'reduce'});
      await context.addInitScript(() => {
        const original = window.fetch.bind(window);
        window.__resultReads = [];
        window.fetch = (url, options = {}) => {
          if (typeof url !== 'string' || !url.startsWith('/api/jobs/result?')) return original(url, options);
          const row = {url, method: options.method || 'GET', aborted: false, completed: false};
          window.__resultReads.push(row);
          options.signal?.addEventListener('abort', () => { row.aborted = true; });
          // The race scenario deliberately delivers an already-pending response
          // despite abort. Actual cancellation is checked in separate scenarios.
          if (window.__deliverLateResult) { options = {...options}; delete options.signal; }
          return original(url, options).finally(() => { row.completed = true; });
        };
      });
      const external = [];
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === origin.origin) return route.continue();
        external.push(new URL(route.request().url()).origin);
        return route.abort();
      });
      page = await context.newPage();
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(config.url + '/login');
      await page.locator('#password').fill(config.password);
      await page.locator('#login-form button').click();
      await page.waitForURL(config.url + '/');
      await page.locator('#message:enabled').waitFor();
      await page.locator('[data-bottom="ops"]').click();
      await page.locator('.finished-job button').nth(1).waitFor();
      page.on('request', request => { if (request.method() !== 'GET') writes.push(new URL(request.url()).pathname); });
      const first = page.locator('.finished-job button').nth(0);
      const second = page.locator('.finished-job button').nth(1);
      const close = async () => {
        await page.locator('#close-report').click();
        await until(page, () => !document.getElementById('report').open);
      };
      const holdFirst = async () => {
        let begun;
        const started = new Promise(resolve => { begun = resolve; });
        const held = new Promise(resolve => { release = resolve; });
        const handler = async route => {
          const response = await route.fetch();
          begun();
          await held;
          await route.fulfill({response}).catch(() => {});
        };
        await page.route('**/api/jobs/result?id=result-first', handler);
        return {started, handler};
      };
      const readCount = () => page.evaluate(() => window.__resultReads.length);
      // Close one result and select the next while the old transport finishes late.
      await page.evaluate(() => { window.__deliverLateResult = true; });
      const held = await holdFirst();
      await first.click();
      await held.started;
      await close();
      await second.click();
      await until(page, () => document.getElementById('report-body').textContent.startsWith('Selected saved result'));
      release();
      await until(page, () => window.__resultReads[0].completed);
      await page.waitForTimeout(200);
      assert.equal(await page.locator('#report-date').innerText(), 'Selected job');
      assert.equal(await page.locator('#report-body').innerText(), 'Selected saved result <img src=x onerror=alert(1)>');
      assert.equal(await page.locator('#report-body img').count(), 0);
      assert.equal(await page.locator('#retry-report').isVisible(), false);
      assert.equal(await page.evaluate(() => window.__resultReads[0].aborted), true);
      await page.unroute('**/api/jobs/result?id=result-first', held.handler);
      await page.evaluate(() => { window.__deliverLateResult = false; });
      const layouts = [];
      for (const width of [320, 390, 430]) {
        await page.setViewportSize({width, height: 844});
        for (const colorScheme of ['dark', 'light']) {
          await page.emulateMedia({colorScheme});
          const bounds = await page.locator('#report').evaluate(el => ({
            width: el.clientWidth, scroll: el.scrollWidth, viewport: innerWidth,
            document: document.documentElement.scrollWidth,
          }));
          assert(bounds.scroll <= bounds.width && bounds.document <= width, JSON.stringify(bounds));
          layouts.push({width, colorScheme});
        }
      }
      await page.setViewportSize({width: 390, height: 844});
      const screenshot = engine + '-selected-result.png';
      await page.screenshot({path: path.join(config.output, screenshot), animations: 'disabled'});
      // Force the normal read-only refresh while the modal is open: its original
      // button will be detached and restoration must find the current one.
      const refreshed = page.waitForResponse(r => new URL(r.url()).pathname === '/api/jobs/activity');
      await page.evaluate(() => document.getElementById('refresh-jobs').click());
      await refreshed;
      await close();
      await until(page, () => document.activeElement?.dataset.resultUrl === '/api/jobs/result?id=result-second');
      // Escape must cancel a genuine fetch and let the owner keep using Jobs.
      const escape = await holdFirst(), escapeIndex = await readCount();
      await first.click();
      await escape.started;
      await page.keyboard.press('Escape');
      await until(page, () => !document.getElementById('report').open);
      assert.equal(await page.evaluate(i => window.__resultReads[i].aborted, escapeIndex), true);
      release();
      await page.unroute('**/api/jobs/result?id=result-first', escape.handler);
      // A real 15-second stalled read must end and offer exactly one manual retry.
      const stalled = await holdFirst(), timeoutIndex = await readCount();
      const began = Date.now();
      await first.click();
      await stalled.started;
      await page.locator('#report-status').filter({hasText: 'could not be loaded'}).waitFor({timeout: 20000});
      const timeoutMs = Date.now() - began;
      assert(timeoutMs >= 14000 && timeoutMs < 20000, String(timeoutMs));
      assert.equal(await readCount(), timeoutIndex + 1, 'No automatic retry');
      assert.equal(await page.evaluate(i => window.__resultReads[i].aborted, timeoutIndex), true);
      assert.equal(await page.locator('#report-body').getAttribute('aria-busy'), 'false');
      await page.setViewportSize({width: 320, height: 844});
      const retryScreenshot = engine + '-result-retry.png';
      await page.screenshot({path: path.join(config.output, retryScreenshot), animations: 'disabled'});
      release();
      await page.unroute('**/api/jobs/result?id=result-first', stalled.handler);
      await page.locator('#retry-report').click();
      await until(page, () => document.getElementById('report-body').textContent === 'First saved result');
      const reads = await page.evaluate(() => window.__resultReads);
      assert.equal(reads.length, timeoutIndex + 2);
      assert.equal(reads[timeoutIndex].url, reads[timeoutIndex + 1].url);
      assert(reads.every(row => row.method === 'GET'));
      assert.equal(await page.locator('#retry-report').isVisible(), false);
      await close();
      // A failed HTTP response must also be retryable without leaking its details.
      const failed = route => route.fulfill({status: 503, json: {error: 'private fixture transport detail'}});
      await page.route('**/api/jobs/result?id=result-first', failed);
      await first.click();
      await page.locator('#retry-report').waitFor();
      assert(!(await page.locator('#report').innerText()).includes('private fixture'));
      await page.unroute('**/api/jobs/result?id=result-first', failed);
      await page.locator('#retry-report').click();
      await until(page, () => document.getElementById('report-body').textContent === 'First saved result');
      await close();
      assert.deepEqual(errors, []);
      assert.deepEqual(writes, []);
      assert.deepEqual(external, []);
      results.push({engine, passed: true, timeoutMs, layouts, screenshot, retryScreenshot,
        checks: ['late result cannot overwrite selected job', 'literal result content', 'close aborts read',
          'Escape aborts read', 'focus returns to result button', 'real 15-second timeout',
          'manual GET retry for same result', 'HTTP failure recovery', 'no mutation or external request']});
      await context.close();
    } catch (error) {
      if (page) await page.screenshot({path: path.join(config.output, engine + '-failure.png')}).catch(() => {});
      throw error;
    } finally { if (release) release(); await browser.close(); }
  }
  console.log(JSON.stringify({all_pass: true, browsers: results}));
})().catch(error => {console.error(error.stack); process.exitCode = 1;});
