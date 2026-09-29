const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const browser = await playwright[config.engine].launch({headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 320, height: 844}, reducedMotion: 'reduce'});
    await context.route('**/*', route => new URL(route.request().url()).origin === config.url ? route.continue() : route.abort());
    const page = await context.newPage(), errors = [], requests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (new URL(request.url()).pathname === '/api/messages' && request.method() === 'POST') requests.push(request.postDataJSON());
    });
    await page.goto(config.url + '/login');
    await page.locator('#password').fill(config.password);
    await page.locator('#login-form button').click();
    await page.waitForURL(config.url + '/');
    await page.locator('#message:enabled').waitFor();
    await page.locator('[data-bottom="settings"]').click();
    await page.locator('#provider-choice').selectOption('gemini');
    await page.locator('[data-bottom="chat"]').click();
    await page.locator('#message').fill('Describe an imaginary small purple cloud.');
    await page.locator('#send:enabled').click();
    await page.locator('.message.assistant.pending').waitFor();
    await page.locator('#stop:visible').click();
    await page.locator('#notice').filter({hasText: 'You can keep writing'}).waitFor();
    await page.locator('.message.assistant .body').filter({hasText: 'Reply stopped.'}).waitFor();
    const next = 'Describe an imaginary small amber cloud.';
    await page.locator('#message').fill(next);
    assert.equal(await page.locator('#send').isEnabled(), false);
    assert.equal(await page.locator('#message').isEnabled(), true);
    assert.equal(await page.locator('#stop').isVisible(), false);
    assert.equal(requests.length, 1);
    const stoppingScreenshot = config.engine + '-reply-stopping.png';
    await page.screenshot({path: path.join(config.output, stoppingScreenshot), animations: 'disabled'});
    // Reload must keep the actual in-flight reservation visible as stopping.
    await page.reload();
    await page.locator('#notice').filter({hasText: 'You can keep writing'}).waitFor();
    await page.locator('#message').fill(next);
    assert.equal(await page.locator('#send').isEnabled(), false);
    async function control(route) {
      const status = await page.evaluate(async route => {
        const session = await (await fetch('/api/session')).json();
        return (await fetch(route, {method: 'POST', headers: {'Content-Type': 'application/json',
          'X-CSRF-Token': session.csrf}, body: '{}'})).status;
      }, route);
      assert.equal(status, 200);
    }
    await control('/api/fixture/release');
    await page.locator('#send:enabled').waitFor();
    assert.equal(await page.locator('#message').inputValue(), next);
    assert.equal(await page.locator('.message.assistant').filter({hasText: 'Late answer must not appear.'}).count(), 0);
    await control('/api/fixture/close');
    const rejected = page.waitForResponse(r => new URL(r.url()).pathname === '/api/messages' && r.status() === 503);
    await page.locator('#send:enabled').click();
    await rejected;
    await page.locator('#notice').filter({hasText: 'Your new message was not saved'}).waitFor();
    assert.equal(await page.locator('#message').inputValue(), next);
    assert.equal(await page.locator('#send').isEnabled(), true);
    assert.equal(requests.length, 2);
    const restartScreenshot = config.engine + '-restart-refused.png';
    await page.screenshot({path: path.join(config.output, restartScreenshot), animations: 'disabled'});
    const retried = page.waitForResponse(r => new URL(r.url()).pathname === '/api/messages' && r.status() === 503);
    await page.locator('#send:enabled').click();
    await retried;
    assert.equal(requests.length, 3);
    assert.deepEqual(requests[2], requests[1], 'A manual retry preserves the rejected request identity');
    const rows = await page.evaluate(async () => (await (await fetch('/api/conversations/' + localStorage.getItem('bob.conversation'))).json()).messages);
    assert.equal(rows.filter(m => m.role === 'user').length, 1);
    assert.equal(rows.at(-1).status, 'cancelled');
    for (const width of [320, 390, 430]) {
      await page.setViewportSize({width, height: 844});
      await page.waitForTimeout(200);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({engine: config.engine, passed: true, stoppingScreenshot, restartScreenshot,
      checks: ['immediate Stop', 'late progress ignored', 'busy until provider returns', 'reload retains stopping state',
        'new draft survives completion', 'restart rejects before persistence', 'manual retry retains identity', 'phone layout']}));
    await context.close();
  } finally { await browser.close(); }
})().catch(error => {console.error(error.stack); process.exitCode = 1;});
