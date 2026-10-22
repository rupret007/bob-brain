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
    const latest = () => page.locator('.message.assistant').last();
    async function command(action) {
      const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/messages' && r.request().method() === 'POST');
      await action();
      const received = await response;
      assert.equal(received.status(), 202);
      const value = await received.json();
      await latest().locator('.body').filter({hasText: value.messages.at(-1).content}).waitFor();
      await page.locator('#conversations:not([disabled])').waitFor({state: 'attached'});
    }
    async function manage() {
      await page.locator('[data-bottom="settings"]').click();
      const button = page.locator('#manage-memory');
      if (!await button.isVisible()) await page.locator('summary').filter({hasText: 'Saved memory'}).click();
      await command(() => button.click());
      await latest().locator('.memory-note').first().waitFor();
    }
    const draft = 'Keep this unsent composer draft';
    await page.locator('#message').fill(draft);
    await manage();
    assert.equal(await latest().locator('.memory-note').count(), 2);
    assert.equal(await latest().locator('img').count(), 0, 'Memory must render literally');
    assert.equal(await page.locator('#message').inputValue(), draft);
    await command(() => latest().getByRole('button', {name: 'Review removal'}).first().click());
    await latest().getByRole('button', {name: 'Keep note', exact: true}).waitFor();
    assert.match(await latest().innerText(), /chat history/);
    const reviewScreenshot = config.engine + '-memory-review.png';
    await latest().scrollIntoViewIfNeeded();
    await page.waitForTimeout(250);
    await page.screenshot({path: path.join(config.output, reviewScreenshot), animations: 'disabled'});
    await command(() => latest().getByRole('button', {name: 'Keep note', exact: true}).click());
    assert.match(await latest().innerText(), /cancelled/);
    await manage();
    assert.equal(await latest().locator('.memory-note').count(), 2);
    await command(() => latest().getByRole('button', {name: 'Review removal'}).first().click());
    const code = await page.evaluate(async () => {
      const session = await (await fetch('/api/session')).json();
      return (await fetch('/api/fixture/change-memory', {method: 'POST', headers: {'Content-Type': 'application/json',
        'X-CSRF-Token': session.csrf}, body: '{}'})).status;
    });
    assert.equal(code, 200);
    await command(() => latest().getByRole('button', {name: 'Remove this note', exact: true}).click());
    assert.match(await latest().innerText(), /changed/);
    await manage();
    assert.equal(await latest().locator('.memory-note').count(), 3);
    await command(() => latest().getByRole('button', {name: 'Review removal'}).first().click());
    await page.reload();
    await latest().getByRole('button', {name: 'Remove this note', exact: true}).waitFor();
    await command(() => latest().getByRole('button', {name: 'Remove this note', exact: true}).click());
    assert.match(await latest().innerText(), /Removed one saved Web Bob note/);
    const confirmation = requests.at(-1);
    const retried = await page.evaluate(async body => {
      const session = await (await fetch('/api/session')).json();
      return (await fetch('/api/messages', {method: 'POST', headers: {'Content-Type': 'application/json',
        'X-CSRF-Token': session.csrf}, body: JSON.stringify(body)})).status;
    }, confirmation);
    assert.equal(retried, 202);
    await manage();
    assert.equal(await latest().locator('.memory-note').count(), 2);
    assert.doesNotMatch(await latest().innerText(), /copper-puffin/);
    assert.match(await latest().innerText(), /<img src=x onerror=alert\(1\)>/);
    const completeScreenshot = config.engine + '-memory-removed.png';
    await latest().scrollIntoViewIfNeeded();
    await page.waitForTimeout(250);
    await page.screenshot({path: path.join(config.output, completeScreenshot), animations: 'disabled'});
    const layouts = [];
    for (const width of [320, 390, 430]) {
      await page.setViewportSize({width, height: 844});
      await page.waitForTimeout(200);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
      layouts.push(width);
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({engine: config.engine, passed: true, reviewScreenshot, completeScreenshot, layouts,
      checks: ['separate review and confirmation', 'literal notes', 'quick action preserves draft', 'cancel preserves notes',
        'changed-file refusal', 'reload preserves proposal', 'request replay idempotent', 'exactly one note removed', 'phone layout']}));
    await context.close();
  } finally { await browser.close(); }
})().catch(error => {console.error(error.stack); process.exitCode = 1;});
