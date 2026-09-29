/* Uncertain-send recovery using synthetic messaging and real browser/HTTP. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const url = new URL(config.url);
  assert.equal(url.hostname, '127.0.0.1');
  assert(!['8787', '1234', '4315', '4316'].includes(url.port));
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
        return value;
      }
      const draft = (await say('draft reply to Alex Morgan: ' + engine + ' synthetic receipt check.')).messages.at(-1).text_draft;
      assert(draft.delivery_available);
      const reply = (await say(draft.confirm_message)).messages.at(-1);
      assert(reply.content.includes('delivery is unconfirmed'));
      const card = page.locator(`.text-draft-card[data-draft-id="${draft.id}"]`);
      await card.getByRole('button', {name: 'Check delivery', exact: true}).waitFor();
      assert.equal(await card.locator('.text-confirmation').count(), 0);
      for (const command of ['cancel text', 'yes wbtxt-invalid']) {
        const answer = (await say(command)).messages.at(-1);
        assert(answer.content.includes('Delivery remains unconfirmed'));
        assert(!answer.content.includes('Nothing sent.'));
        assert.equal(await card.getAttribute('data-state'), 'delivery_unconfirmed');
        await card.getByRole('button', {name: 'Check delivery', exact: true}).waitFor();
      }
      for (const width of [320, 390, 430]) {
        await page.setViewportSize({width, height: 844});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        assert.equal(await card.evaluate(el => el.scrollWidth > el.clientWidth), false);
      }
      await page.reload();
      const response = page.waitForResponse(r => r.url() === config.url + '/api/messages' && r.request().method() === 'POST');
      await card.getByRole('button', {name: 'Check delivery', exact: true}).click();
      assert((await (await response).json()).messages.at(-1).content.includes('nothing was resent'));
      await page.locator(`.text-draft-card[data-draft-id="${draft.id}"][data-state="sent"]`).waitFor();
      assert.equal(await card.getByRole('button', {name: 'Check delivery', exact: true}).count(), 0);
      const cancelled = (await say('cancel text draft ' + draft.id)).messages.at(-1);
      assert(cancelled.content.includes('already verified sent'));
      assert(cancelled.content.includes('cannot recall'));
      assert(!cancelled.content.includes('Nothing sent.'));
      await page.reload();
      await page.locator(`.text-draft-card[data-draft-id="${draft.id}"][data-state="sent"]`).waitFor();
      await page.setViewportSize({width: 390, height: 844});
      await card.scrollIntoViewIfNeeded();
      const screenshot = engine + '-delivery-recovered.png';
      await page.screenshot({path: path.join(config.output, screenshot), animations: 'disabled'});
      assert.deepEqual(errors, []);
      results.push({engine, passed: true, screenshot, checks: ['uncertain receipt', 'cancel and malformed yes preserve uncertain outcome', 'no reusable confirmation', 'check after reload', 'verified receipt without resend', 'cannot cancel a sent message', 'persisted sent card', '320/390/430 layout']});
      await context.close();
    } finally { await browser.close(); }
  }
  console.log(JSON.stringify({all_pass: true, browsers: results}));
})().catch(e => {console.error(e.stack); process.exitCode = 1;});
