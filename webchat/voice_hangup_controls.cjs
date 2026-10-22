/* Offline activation races through the real app/voice controller. Synthetic
   provider transport only; transcript saves deliberately remain pending. */
const assert = require('node:assert/strict');

async function until(page, predicate) {
  const deadline = Date.now() + 5000;
  while (!(await page.evaluate(predicate))) {
    assert.ok(Date.now() < deadline, 'Hangup resources/state did not settle');
    await page.waitForTimeout(25);
  }
}

module.exports = async function proveHangupControls(browser, config) {
  const results = [];
  for (const mode of ['phone-mouse', 'resized-phone-mouse', 'phone-touch', 'desktop-mouse', 'keyboard']) {
    const mobile = mode !== 'desktop-mouse';
    const context = await browser.newContext({viewport: mobile ? {width: 390, height: 844} : {width: 1280, height: 900},
      isMobile: mobile, hasTouch: mobile, deviceScaleFactor: 1});
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let releaseSave;
    const saveBarrier = new Promise(resolve => { releaseSave = resolve; });
    try {
      await page.addInitScript(() => {
        const NativeAudio = window.AudioContext;
        window.hangupProof = {contexts: [], tracks: [], sockets: [], events: [], stops: 0, ends: 0, saves: 0};
        window.AudioContext = class extends NativeAudio {
          constructor(...args) { super(...args); hangupProof.contexts.push(this); }
        };
        Object.defineProperty(Object.getPrototypeOf(navigator.mediaDevices), 'getUserMedia', {configurable: true,
          value: async () => {
            const stream = hangupProof.contexts.at(-1).createMediaStreamDestination().stream;
            hangupProof.tracks.push(...stream.getTracks()); return stream;
          }});
        window.WebSocket = class {
          static OPEN = 1;
          constructor() {
            this.readyState = 1; this.bufferedAmount = 0; hangupProof.sockets.push(this);
            setTimeout(() => this.onopen?.(), 10);
          }
          emit(value) { this.onmessage?.({data: JSON.stringify(value)}); }
          send(raw) { if (JSON.parse(raw).setup) setTimeout(() => this.emit({setupComplete: {}}), 10); }
          close() { this.readyState = 3; }
        };
        for (const type of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'keydown', 'keyup']) {
          document.addEventListener(type, event => {
            if (event.target.id === 'end-call') hangupProof.events.push({type, trusted: event.isTrusted});
          }, true);
        }
        document.addEventListener('DOMContentLoaded', () => {
          if (!window.BobVoice) return; // Login page has no voice controller.
          const stop = BobVoice.prototype.stop;
          BobVoice.prototype.stop = function(...args) {
            if (this.active) hangupProof.stops++;
            return stop.apply(this, args);
          };
        });
      });
      await page.route('**/api/voice/start', route => route.fulfill({json: {call_id: 'offline-hangup', token: 'fixture',
        model: 'fixture', url: 'wss://fixture.invalid', expires_at: Date.now() / 1000 + 600}}));
      await page.route('**/api/voice/transcript', async route => {
        await page.evaluate(() => hangupProof.saves++);
        await saveBarrier;
        await route.fulfill({json: {ok: true}});
      });
      await page.route('**/api/voice/end', async route => {
        await page.evaluate(() => hangupProof.ends++);
        await route.fulfill({json: {ok: true}});
      });
      await page.route('**/api/voice/pulse', route => route.fulfill({json: {ok: true}}));
      await page.goto(config.url + '/login');
      await page.locator('#password').fill(config.password);
      await page.locator('#login-form button').click(); await page.waitForURL(config.url + '/');
      await page.locator('#message:enabled').waitFor();
      await page.locator('#live-call').click();
      await until(page, () => document.querySelector('#call-dialog').dataset.phase === 'listening');
      assert.equal(await page.locator('#end-call').textContent(), 'Hang up');
      await page.evaluate(() => {
        const socket = hangupProof.sockets[0];
        for (let n = 0; n < 7; n++) socket.emit({serverContent: {inputTranscription: {text: 'Synthetic request'},
          outputTranscription: {text: 'Synthetic answer. '.repeat(24)}, turnComplete: true}});
      });
      await until(page, () => hangupProof.saves > 0);
      if (mode === 'resized-phone-mouse') await page.setViewportSize({width: 1280, height: 900});
      if (mode.endsWith('mouse')) {
        const box = await page.locator('#end-call').boundingBox();
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.down();
        // Force an ordinary provider state update strictly inside a trusted
        // press/release. No DOM activation, forced click or retry is used.
        await page.evaluate(() => hangupProof.sockets[0].emit({serverContent: {turnComplete: true}}));
        await page.mouse.up();
      } else if (mode === 'phone-touch') {
        await page.locator('#end-call').tap();
      } else {
        await page.locator('#end-call').focus(); await page.keyboard.press('Enter');
      }
      const immediate = await page.evaluate(() => ({stops: hangupProof.stops,
        tracks: hangupProof.tracks.map(track => track.readyState), sockets: hangupProof.sockets.map(socket => socket.readyState),
        events: hangupProof.events}));
      assert.equal(immediate.stops, 1, mode + ': one activation must stop the active call');
      assert.ok(immediate.tracks.length && immediate.tracks.every(state => state === 'ended'));
      assert.deepEqual(immediate.sockets, [3]);
      assert.equal(immediate.events.filter(event => event.type === 'click' && event.trusted).length, 1);
      await until(page, () => hangupProof.ends === 1 && hangupProof.contexts.every(audio => audio.state === 'closed'));
      assert.match(await page.locator('#call-status').textContent(), /saving transcript/);
      assert.equal(await page.locator('#end-call').textContent(), 'Back to chat');
      assert.equal(await page.locator('#live-call').getAttribute('aria-pressed'), 'false');
      releaseSave();
      await until(page, () => document.querySelector('#call-status').textContent.includes('transcript saved'));
      assert.deepEqual(errors, []);
      results.push({mode, all_pass: true, synthetic_transport: true, cleanup_before_save: true, ...immediate});
    } finally { releaseSave(); await context.close(); }
  }
  return results;
};
