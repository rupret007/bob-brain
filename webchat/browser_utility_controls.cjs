/* Real UI events with synthetic clipboard/speech hardware; zero model/message sends. */
const fs = require('node:fs');
const assert = require('node:assert/strict');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
async function until(page, predicate) {
  const deadline = Date.now() + 5000;
  while (!(await page.evaluate(predicate))) {
    assert(Date.now() < deadline, 'Utility control did not settle');
    await page.waitForTimeout(30);
  }
}
(async () => {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const origin = new URL(config.url);
  assert.equal(origin.hostname, '127.0.0.1');
  assert(!['8787', '1234', '4315', '4316'].includes(origin.port));
  const browsers = [];
  for (const engine of ['chromium', 'webkit']) {
    const browser = await playwright[engine].launch({headless:true});
    try {
      const context = await browser.newContext({viewport:{width:390, height:844}});
      await context.route('**/*', route => new URL(route.request().url()).origin === origin.origin ? route.continue() : route.abort());
      await context.addInitScript(() => {
        window.utility = {copies:[], spoken:[], cancelled:0, recognizers:[], failCopy:false, failStart:false};
        // Freeze civil time in daytime; timers continue using real Date.now().
        const NativeDate = Date;
        window.Date = class extends NativeDate { constructor(...args) { super(...(args.length ? args : ['2026-10-01T19:00:00Z'])); } };
        Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText:async text => {
          if (utility.failCopy) throw new Error('synthetic clipboard denial'); utility.copies.push(text);
        }}});
        Object.defineProperty(window, 'speechSynthesis', {configurable:true, value:{
          getVoices:() => [{name:'English fixture',lang:'en-US'}],
          cancel:() => utility.cancelled++, speak:utter => utility.spoken.push(utter),
        }});
        window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } };
        window.SpeechRecognition = class {
          constructor() { this.started = 0; this.stopped = 0; utility.recognizers.push(this); }
          start() { if (utility.failStart) throw new Error('synthetic speech denial'); this.started++; }
          stop() { this.stopped++; this.onend?.(); }
        };
      });
      const page = await context.newPage(), errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      const code = 'if ready:\n    print("<tag> **literal** `tick`")\n    # preserve indentation';
      const content = '**Useful reply.**\n\n```python\n' + code + '\n```';
      await page.route('**/api/conversations/*', async route => {
        assert.equal(route.request().method(), 'GET');
        const response = await route.fetch(), value = await response.json();
        value.messages = [{id:'utility-fixture',role:'assistant',status:'done',content,provider:'fixture'}];
        await route.fulfill({response,json:value});
      });
      await page.goto(config.url + '/login');
      await page.locator('#password').fill(config.password);
      await page.locator('#login-form button').click();
      await page.waitForURL(config.url + '/');
      await page.locator('#message:enabled').waitFor();
      page.on('request', request => { if (request.method() !== 'GET') writes.push(new URL(request.url()).pathname); });
      await page.locator('.copy-code').click();
      await until(page, () => utility.copies.length === 1);
      assert.equal(await page.evaluate(() => utility.copies[0]), code);
      assert.equal(await page.locator('.code-block code br, .code-block code strong, .code-block code tag').count(), 0);
      await page.locator('.msg-copy').click();
      await until(page, () => utility.copies.length === 2);
      assert.equal(await page.evaluate(() => utility.copies[1]), content);
      await page.locator('.message.assistant .body').click({button:'right'});
      await page.locator('.msg-menu [data-act="copy"]').click();
      await until(page, () => utility.copies.length === 3);
      assert.equal(await page.evaluate(() => utility.copies[2]), content);
      assert.equal(await page.locator('.msg-menu').count(), 0);
      await page.evaluate(() => { utility.failCopy = true; });
      await page.locator('.copy-code').click();
      await page.locator('#notice').filter({hasText:'Could not copy'}).waitFor();
      await page.locator('#message').fill('Keep this');
      await page.locator('#mic').click();
      assert.equal(await page.locator('#mic').getAttribute('aria-pressed'), 'true');
      await page.evaluate(() => utility.recognizers.at(-1).onresult({results:[[{transcript:'first draft'}]]}));
      assert.equal(await page.locator('#message').inputValue(), 'Keep this first draft');
      await page.evaluate(() => utility.recognizers.at(-1).onresult({results:[[{transcript:'corrected draft'}]]}));
      assert.equal(await page.locator('#message').inputValue(), 'Keep this corrected draft');
      await page.locator('#mic').click();
      assert.equal(await page.locator('#mic').getAttribute('aria-pressed'), 'false');
      await page.evaluate(() => utility.recognizers.at(-1).onresult({results:[[{transcript:'stale result'}]]}));
      assert.equal(await page.locator('#message').inputValue(), 'Keep this corrected draft');
      await page.locator('#mic').click();
      await page.evaluate(() => { const r=utility.recognizers.at(-1); r.onerror({error:'not-allowed'}); r.onend(); });
      await page.locator('#notice').filter({hasText:'Microphone blocked'}).waitFor();
      assert.equal(await page.locator('#mic').getAttribute('aria-pressed'), 'false');
      await page.evaluate(() => { utility.failStart = true; });
      await page.locator('#mic').click();
      await page.locator('#notice').filter({hasText:'Could not start voice input'}).waitFor();
      await page.evaluate(() => { utility.failStart = false; });
      await page.locator('#mic').click();
      await page.setViewportSize({width:900,height:844}); // Composer read-aloud is a desktop control.
      await page.locator('#speak').click();
      await until(page, () => utility.spoken.length === 1);
      assert.equal(await page.locator('#mic').getAttribute('aria-pressed'), 'false');
      assert.equal(await page.locator('#speak').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.evaluate(() => utility.spoken[0].text), 'Useful reply.');
      await page.locator('#speak').click();
      assert.equal(await page.locator('#speak').getAttribute('aria-pressed'), 'false');
      await page.locator('#speak').click();
      await until(page, () => utility.spoken.length === 2);
      await page.evaluate(() => utility.spoken.at(-1).onend());
      assert.equal(await page.locator('#speak').getAttribute('aria-pressed'), 'false');
      await page.locator('.message.assistant .body').click({button:'right'});
      await page.locator('.msg-menu [data-act="speak"]').click();
      await until(page, () => utility.spoken.length === 3);
      await page.evaluate(() => { delete window.SpeechRecognition; delete window.webkitSpeechRecognition; });
      await page.locator('#mic').click();
      await page.locator('#notice').filter({hasText:'Keyboard dictation always works'}).waitFor();
      await page.evaluate(() => { delete window.speechSynthesis; });
      await page.locator('#speak').click();
      await page.locator('#notice').filter({hasText:'Read-aloud is not supported'}).waitFor();
      assert.deepEqual(writes, [], 'Utility controls must not send messages or other writes');
      assert.deepEqual(errors, []);
      browsers.push({engine,all_pass:true,synthetic_clipboard_and_speech:true,writes:0,
        checks:['message/code copy and denied clipboard','dictation preserves draft, interim correction, stop, stale event',
          'microphone denial, start failure, unsupported fallback','read aloud, microphone stop, toggle/end, context action, unsupported fallback']});
      await context.close();
    } finally { await browser.close(); }
  }
  console.log(JSON.stringify({all_pass:true,browsers,physical_audio_verified:false}));
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
