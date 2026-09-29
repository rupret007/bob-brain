/* Real browser, isolated synthetic messaging only. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const url = new URL(config.url);
  assert.equal(url.hostname, '127.0.0.1');
  assert(!['8787', '1234', '4315'].includes(url.port));
  const results = [];
  for (const engine of ['chromium', 'webkit']) {
    const browser = await playwright[engine].launch({headless: true});
    try {
      const context = await browser.newContext({viewport: {width: 390, height: 844}, reducedMotion: 'reduce'});
      await context.route('**/*', route => new URL(route.request().url()).origin === url.origin ? route.continue() : route.abort());
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(config.url + '/login');
      await page.locator('#password').fill(config.password);
      await page.locator('#login-form button').click();
      await page.waitForURL(config.url + '/');
      async function say(text) {
        await page.locator('#message:enabled').fill(text);
        const pending = page.waitForResponse(r => r.url() === config.url + '/api/messages' && r.request().method() === 'POST');
        await page.locator('#send:enabled').click();
        const response = await pending;
        assert.equal(response.status(), 202);
        const value = await response.json();
        await page.locator('#attach-plus:enabled').waitFor();
        return value.messages.at(-1);
      }
      const digest = await say('digest Instinct');
      for (const label of ['Bills / deadlines', 'Security', 'Appointments']) assert(digest.content.includes(label + ': 1'));
      const draft = await say('draft reply to Instinct');
      assert.equal(draft.text_draft.state, 'read_only');
      assert.equal(draft.text_draft.confirm_message, null);
      const card = page.locator('.text-draft-card').last();
      await card.getByText('Instinct is read-only.', {exact: false}).waitFor();
      assert.equal(await page.locator('.text-confirmation').count(), 0);
      assert.equal(await page.getByRole('button', {name: 'Put confirmation in chat'}).count(), 0);
      await card.getByRole('button', {name: 'Edit draft', exact: true}).click();
      const editing = page.locator('.text-draft-card[data-state="editing"]');
      await editing.getByLabel('Text body').fill('Please summarize the appointment choices.');
      await editing.getByRole('button', {name: 'Review new draft'}).click();
      const revised = page.locator('.text-draft-card[data-state="read_only"]').last();
      await revised.waitFor();
      assert((await revised.locator('.text-draft-body').textContent()).includes('Please summarize the appointment choices.'));
      assert.equal(await page.locator('.text-confirmation').count(), 0);
      assert((await say('yes wbtxt-' + 'a'.repeat(32))).content.includes('Instinct is read-only'));
      await page.reload();
      await page.locator('.text-draft-card[data-state="read_only"]').last().waitFor();
      assert.equal(await page.locator('.text-confirmation').count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      const screenshot = engine + '-instinct-read-only.png';
      await page.locator('.text-draft-card').last().scrollIntoViewIfNeeded();
      await page.screenshot({path: path.join(config.output, screenshot), animations: 'disabled'});
      await page.locator('.text-draft-card').last().getByRole('button', {name: 'Cancel draft'}).click();
      await page.locator('.text-draft-card[data-state="cancelled"]').last().waitFor();
      assert.deepEqual(errors, []);
      results.push({engine, passed: true, screenshot, checks: ['sourced digest flags', 'draft without send control', 'edit stays read-only', 'confirmation refused', 'reload preserves read-only', 'cancel', 'phone overflow']});
      await context.close();
    } finally { await browser.close(); }
  }
  console.log(JSON.stringify({all_pass: true, browsers: results}));
})().catch(e => { console.error(e.stack); process.exitCode = 1; });
