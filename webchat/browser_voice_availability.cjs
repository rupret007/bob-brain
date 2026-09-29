"use strict";
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
async function until(page, predicate) {
  // Keep CSP enabled: older WebKit's waitForFunction internally uses eval.
  const deadline = Date.now() + 5000;
  while (!(await page.evaluate(predicate))) {
    assert.ok(Date.now() < deadline, 'Voice resources did not close within five seconds');
    await page.waitForTimeout(50);
  }
}
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  const config = JSON.parse(input), browsers = [];
  for (const engine of ['chromium', 'webkit']) {
    const browser = await playwright[engine].launch({headless: true});
    try {
      const page = await browser.newPage({viewport: {width: 320, height: 844}}), errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.addInitScript(() => {
        window.voiceAvailability = {starts: 0, ends: 0, sockets: [], contexts: [], tracks: [], closeCalls: 0, closeResolved: 0, closeErrors: [],
          reason: 'Your prepayment credits are depleted. private-fixture-details https://private.example/secret'};
        const NativeAudio = window.AudioContext;
        window.AudioContext = class extends NativeAudio {
          constructor(...args) { super(...args); voiceAvailability.contexts.push(this); }
          close() {
            voiceAvailability.closeCalls++;
            const closing = super.close();
            closing.then(() => voiceAvailability.closeResolved++, error => voiceAvailability.closeErrors.push(error.name));
            return closing;
          }
        };
        Object.defineProperty(Object.getPrototypeOf(navigator.mediaDevices), 'getUserMedia', {
          configurable: true, value: async () => {
            // A real microphone is independent of the output graph. Feeding a
            // context's own destination back into its capture worklet creates a
            // synthetic feedback graph that can keep WebKit's state running.
            const microphone = new NativeAudio();
            voiceAvailability.contexts.push(microphone);
            const unlocked = microphone.resume();
            const stream = microphone.createMediaStreamDestination().stream;
            for (const track of stream.getTracks()) {
              const stop = track.stop.bind(track);
              track.stop = () => { stop(); microphone.close().catch(() => {}); };
            }
            voiceAvailability.tracks.push(...stream.getTracks());
            await unlocked;
            return stream;
          },
        });
        window.WebSocket = class {
          static OPEN = 1;
          constructor() {
            this.readyState = 1; this.bufferedAmount = 0;
            voiceAvailability.sockets.push(this);
            setTimeout(() => { this.onopen?.(); this.onclose?.({code: 1011, reason: voiceAvailability.reason}); }, 20);
          }
          send() {}
          close() { this.readyState = 3; }
        };
      });
      await page.route('**/api/voice/start', async route => {
        await page.evaluate(() => voiceAvailability.starts++);
        await route.fulfill({json: {call_id: 'synthetic-fixture', token: 'synthetic-fixture',
          model: 'models/synthetic-fixture', url: 'wss://fixture.invalid', expires_at: Date.now() / 1000 + 600}});
      });
      await page.route('**/api/voice/end', async route => {
        await page.evaluate(() => voiceAvailability.ends++);
        await route.fulfill({json: {ok: true}});
      });
      await page.goto(config.url + '/login');
      await page.locator('#password').fill(config.password);
      await page.locator('#login-form button').click();
      await page.waitForURL(config.url + '/');
      await page.locator('#message:enabled').waitFor();
      await page.locator('#live-call').click();
      await page.locator('#call-status').filter({hasText: 'Live voice is out of prepaid credits.'}).waitFor();
      await until(page, () => voiceAvailability.ends === 1 &&
        voiceAvailability.tracks.every(t => t.readyState === 'ended') &&
        voiceAvailability.contexts.every(c => c.state === 'closed'));
      assert.match(await page.locator('#call-status').textContent(), /Google AI Studio/);
      assert.doesNotMatch(await page.locator('#call-dialog').textContent(), /private-fixture|private.example|secret/);
      assert.match(await page.locator('#call-hint').textContent(), /Back to chat/);
      assert.equal(await page.locator('#end-call').textContent(), 'Back to chat');
      assert.equal(await page.locator('#live-call').getAttribute('aria-pressed'), 'false');
      const box = await page.locator('#end-call').boundingBox();
      assert.ok(box.width >= 44 && box.height >= 44 && box.x >= 0 && box.x + box.width <= 320);
      await page.waitForTimeout(200);
      assert.equal(await page.evaluate(() => voiceAvailability.starts), 1);
      await page.screenshot({path: path.join(config.output, engine + '-credit-recovery.png'), animations: 'disabled'});
      // Keyboard recovery must leave the composer usable without starting a call.
      await page.locator('#end-call').focus(); await page.keyboard.press('Enter');
      assert.equal(await page.locator('#call-dialog').isVisible(), false);
      await page.locator('#message').fill('Unsent draft survives voice recovery');
      await page.evaluate(() => { voiceAvailability.reason = 'private-fixture-details unknown provider error'; });
      await page.locator('#live-call').click();
      await page.locator('#call-status').filter({hasText: 'Call disconnected. Return to chat to start another call.'}).waitFor();
      await until(page, () => voiceAvailability.ends === 2);
      assert.doesNotMatch(await page.locator('#call-dialog').textContent(), /private-fixture|credits/);
      await page.locator('#end-call').click();
      assert.equal(await page.locator('#message').inputValue(), 'Unsent draft survives voice recovery');
      assert.equal(await page.evaluate(() => voiceAvailability.starts), 2);
      assert.equal(await page.evaluate(() => voiceAvailability.sockets.every(s => s.readyState === 3)), true);
      assert.deepEqual(errors, []);
      browsers.push({engine, all_pass: true, page_errors: [], synthetic_transport: true,
        checks: ['fixed credit explanation; raw details hidden', '44px visible keyboard recovery',
          'no automatic retry; composer preserved', 'unknown close stays generic; microphone/socket cleanup']});
    } catch (error) {
      const page = browser.contexts()[0]?.pages()[0];
      if (page) {
        await page.screenshot({path: path.join(config.output, engine + '-failure.png'), animations: 'disabled'}).catch(() => {});
        const resources = await page.evaluate(() => ({starts: voiceAvailability.starts, ends: voiceAvailability.ends,
          tracks: voiceAvailability.tracks.map(t => t.readyState), contexts: voiceAvailability.contexts.map(c => c.state),
          sockets: voiceAvailability.sockets.map(s => s.readyState), closeCalls: voiceAvailability.closeCalls,
          closeResolved: voiceAvailability.closeResolved, closeErrors: voiceAvailability.closeErrors})).catch(() => ({}));
        error.message += ' ' + engine + ' ' + JSON.stringify(resources);
      }
      throw error;
    } finally { await browser.close(); }
  }
  console.log(JSON.stringify({all_pass: true, browsers}));
}).on('error', error => { console.error(error.message); process.exitCode = 1; });
process.on('unhandledRejection', error => { console.error(error.message); process.exitCode = 1; });
