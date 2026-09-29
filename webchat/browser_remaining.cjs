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
        return value;
      }
      const body = engine + ' check reminder';
      for (const [question, expected] of [
        ['Can you send texts?', 'confirm that draft separately'],
        ['Is my memory private?', 'future model context'],
        ['Can you text Instinct?', 'cannot be sent from Web Bob'],
      ]) {
        const value = await say(question);
        assert.equal(value.messages.at(-1).provider, 'capabilities');
        assert(value.messages.at(-1).content.includes(expected));
        await page.locator('.message.assistant').filter({hasText: expected}).last().waitFor();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      }
      const saved = await say('remind me to ' + body + ' in 1 second');
      assert.equal(saved.messages.at(-1).provider, 'reminders');
      await page.locator('.message.assistant').filter({hasText: 'Reminder: ' + body}).waitFor({timeout: 8000});
      const repeating = await say('remind me every 1 minute to ' + engine + ' stretch');
      const id = repeating.messages.at(-1).content.match(/ID ([0-9a-f]{16})/)[1];
      await page.locator('[data-bottom="ops"]').click();
      await page.locator('#reminder-cards').getByText(engine + ' stretch', {exact: true}).waitFor();
      await page.locator('#teammate-cards').getByText('Karen', {exact: true}).waitFor();
      assert((await page.locator('#teammate-cards').textContent()).includes('pending'));
      const reminder = page.locator('#reminder-cards article').filter({hasText: engine + ' stretch'});
      await reminder.getByRole('button', {name: 'Open reminder chat'}).click();
      await page.locator('#view-chat:visible').waitFor();
      assert((await say('cancel reminder ' + id)).messages.at(-1).content.includes('cancelled'));
      assert((await say('band desk digest')).messages.at(-1).content.includes('messages read'));
      await page.locator('[data-bottom="ops"]').click();
      await page.locator('#refresh-jobs:enabled').waitFor();
      const screenshot = engine + '-reminders-teammates.png';
      await page.locator('#reminders-title').scrollIntoViewIfNeeded();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.screenshot({path: path.join(config.output, screenshot), animations: 'disabled'});
      assert.deepEqual(errors, []);
      results.push({engine, passed: true, screenshot, checks: ['capability answers visible without model calls', 'real due notification without worker scheduler', 'recurring reminder visible in Jobs', 'open reminder chat', 'cancel', 'saved Karen status', 'private band digest', 'phone overflow']});
      await context.close();
    } finally { await browser.close(); }
  }
  console.log(JSON.stringify({all_pass: true, browsers: results}));
})().catch(e => { console.error(e.stack); process.exitCode = 1; });
