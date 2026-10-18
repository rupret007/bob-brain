/* Isolated authenticated M1 flow. Config contains ephemeral local credentials. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
(async () => {
  assert.equal(new URL(config.url).hostname, '127.0.0.1');
  const browser = await chromium.launch({headless: true});
  try {
    const context = await browser.newContext({viewport:{width:390,height:844},isMobile:true});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(config.url + '/login');
    await page.locator('#password').fill(config.password);
    await page.locator('#login-form button').click();
    await page.waitForURL(config.url + '/');
    async function say(text, expected) {
      const before = await page.locator('#messages .assistant').count();
      await page.locator('#message').fill(text);
      await page.locator('#send').click();
      await page.waitForFunction(n => document.querySelectorAll('#messages .assistant').length > n, before);
      const reply = page.locator('#messages .assistant').last();
      await reply.filter({hasText:expected}).waitFor();
      return await reply.innerText();
    }
    await say('remember that my harmless trial preference is copper sailboat', 'Reply');
    await say('yes, save memory', 'Saved to durable memory');
    await page.reload();
    await page.locator('.composer-dock').waitFor();
    await say('show my saved memories', 'copper sailboat');
    const status = await say('run Stack Ops', 'read-only observations');
    for (const source of ['MONITOR.md','NEEDS_JEFF.md','MORNING_DIGEST.md','HANDOFF.md']) assert(status.includes(source), source);
    assert(status.includes('stale'), 'Stale source evidence must remain visible');
    const proposal = await say('storypool kick dashboard', 'No action has run');
    const token = proposal.match(/wbsp-[a-f0-9]{32}/)[0];
    await say('cancel ' + token, 'No action ran');
    await say('yes ' + token, 'already consumed');
    for (const width of [360,390,430]) {
      await page.setViewportSize({width,height:844});
      for (const tab of ['chat','ops','lanes','settings']) {
        await page.locator(`[data-bottom="${tab}"]`).click();
        await page.locator(`[data-view="${tab}"]:not([hidden])`).waitFor();
        await page.locator(`[data-view="${tab}"]`).evaluate(v => Promise.all(v.getAnimations().map(a => a.finished)));
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${tab} overflow at ${width}`);
      }
      await page.locator('[data-bottom="chat"]').click();
      if (config.screenshots) await page.screenshot({path:path.join(config.screenshots, `webbob-m1-${width}.png`),fullPage:true});
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
