/* Offline browser regressions against the disposable media_browser_test.py server. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, webkit, devices } = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
const arg = (name) => process.argv[process.argv.indexOf(name) + 1];
const url = arg('--url');
const root = arg('--fixtures');
const screenshots = process.argv.includes('--screenshots') ? arg('--screenshots') : null;

async function run(engine, browserType) {
  const browser = await browserType.launch({ headless: true });
  const context = await browser.newContext({ ...devices['iPhone 13'], acceptDownloads: true });
  const page = await context.newPage();
  const failures = [], posts = [];
  page.on('pageerror', (error) => failures.push(error.message));
  await context.route('**/*', async (route) => {
    if (!route.request().url().startsWith(url + '/')) {
      failures.push('Unexpected non-fixture network request');
      return route.abort();
    }
    return route.continue();
  });
  page.on('request', (request) => {
    if (request.url().endsWith('/api/messages') && request.method() === 'POST') posts.push(request.postDataJSON());
  });
  await page.addInitScript(() => {
    window.mediaCspFailures = [];
    document.addEventListener('securitypolicyviolation', (event) => window.mediaCspFailures.push(event.violatedDirective));
    // A media upload must pass the File directly; prohibit JS base64 copies.
    FileReader.prototype.readAsDataURL = () => { throw new Error('Media used FileReader base64'); };
  });
  // WebKit's injected waitForFunction uses eval, which the real CSP forbids.
  const until = async (predicate, value) => {
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) {
      if (await page.evaluate(predicate, value)) return;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    throw new Error('Timed out: ' + String(predicate));
  };
  const expectChips = async (count) => until((n) => document.querySelectorAll('#attach-preview .attach-chip').length === n, count);
  const idle = async () => until(() => !document.querySelector('#attach-plus').disabled);
  const switchTo = async (id) => {
    await page.locator('#open-chats').click();
    await page.locator('#conversations-dialog').selectOption(id);
    await until((value) => document.querySelector('#conversations').value === value, id);
    await idle();
  };
  try {
    await page.goto(url + '/login');
    await page.locator('#password').fill(fs.readFileSync(path.join(root, 'conductor/webchat/.password'), 'utf8').trim());
    await page.locator('#login-form button').click();
    await page.waitForURL(url + '/');
    await idle();
    const initialCid = await page.locator('#conversations').inputValue();
    // Give each engine a separate conversation using the actual phone dialog.
    await page.locator('#open-chats').click();
    await page.locator('#new-chat-dialog').click();
    await idle();
    await until((prior) => document.querySelector('#conversations').value !== prior, initialCid);
    const cid = await page.locator('#conversations').inputValue();
    await page.locator('#message').fill('Draft for the photo and video');
    await page.locator('#attach-input').setInputFiles([
      { name: 'photo.png', mimeType: 'image/png', buffer: fs.readFileSync(path.join(root, 'photo.png')) },
      { name: engine === 'webkit' ? 'clip.MOV' : 'clip.webm', mimeType: '', buffer: fs.readFileSync(path.join(root, engine === 'webkit' ? 'clip.mov' : 'clip.webm')) },
      { name: 'notes.txt', mimeType: 'image/png', buffer: fs.readFileSync(path.join(root, 'notes.txt')) },
      { name: 'notes.pdf', mimeType: 'application/pdf', buffer: fs.readFileSync(path.join(root, 'notes.pdf')) },
    ]);
    await expectChips(4); await idle();
    await until(() => document.querySelector('#attach-preview img')?.naturalWidth > 0);
    const target = await page.locator('.attach-remove').first().boundingBox();
    assert(target.width >= 44 && target.height >= 44, 'remove target is at least 44px');
    await page.locator('[data-chip="status"]').click();
    await idle();
    assert.deepEqual(posts.at(-1).attachments, [], 'quick actions must not consume staged media');
    assert.equal(await page.locator('#message').inputValue(), 'Draft for the photo and video');
    await expectChips(4);
    // Switch away/back: neither staged uploads nor text follow the quick command.
    await page.locator('#open-chats').click();
    await page.locator('#new-chat-dialog').click();
    await until((prior) => document.querySelector('#conversations').value !== prior, cid);
    await expectChips(0);
    assert.equal(await page.locator('#message').inputValue(), '');
    await switchTo(cid); await expectChips(4);
    assert.equal(await page.locator('#message').inputValue(), 'Draft for the photo and video');
    // Submit attachment-only and force a lost response. Retry must be idempotent.
    await page.locator('#message').fill('');
    await page.route('**/api/messages', async (route) => {
      const response = await route.fetch();
      await response.dispose();
      await route.abort('failed');
    }, { times: 1 });
    await page.locator('#send').click();
    await until(() => document.querySelector('#notice').textContent.length > 0);
    await expectChips(4);
    await until(() => !document.querySelector('#send').disabled);
    const firstId = posts.at(-1).request_id;
    await page.locator('#send').click();
    await expectChips(0); await idle();
    assert.equal(posts.at(-1).request_id, firstId, 'retry must reuse exact request id');
    await page.locator('.message.assistant .message-attachments video').waitFor();
    assert.equal(await page.locator('.message.user .message-attachment').count(), 4);
    assert.equal(await page.locator('.message.assistant .message-attachment').count(), 4);
    const video = page.locator('.message.assistant video');
    await video.evaluate(async (element) => { element.muted = true; await element.play(); });
    await until(() => document.querySelector('.message.assistant video').readyState >= 2);
    await video.evaluate((element) => { element.pause(); element.currentTime = 1; });
    await until(() => {
      const element = document.querySelector('.message.assistant video');
      return !element.seeking && element.currentTime >= .9;
    });
    assert(await video.evaluate((element) => element.playsInline));
    const downloadLink = page.locator('.message.assistant .attach-download').filter({ hasText: 'notes.txt' });
    const [download] = await Promise.all([page.waitForEvent('download'), downloadLink.click()]);
    assert.equal(download.suggestedFilename(), 'notes.txt');
    assert.equal(fs.readFileSync(await download.path(), 'utf8'), 'A file for the offline browser fixture.');
    await page.reload(); await idle();
    await page.locator('.message.assistant .message-attachments video').waitFor();
    assert.equal(await page.locator('.message.user .message-attachment').count(), 4);
    // Upload failure restores composer and permits retry; no phantom chip.
    await page.route('**/api/media/upload', (route) => route.fulfill({ status: 413, contentType: 'application/json', body: '{"error":"Fixture too large"}' }), { times: 1 });
    await page.locator('#attach-input').setInputFiles(path.join(root, 'notes.txt'));
    await until(() => document.querySelector('#notice').textContent.includes('Fixture too large'));
    await expectChips(0); await idle();
    let releaseUpload;
    const heldUpload = new Promise((resolve) => { releaseUpload = resolve; });
    await page.route('**/api/media/upload', async (route) => { await heldUpload; await route.continue(); }, { times: 1 });
    await page.locator('#attach-input').setInputFiles(path.join(root, 'notes.txt'));
    await until(() => document.querySelector('#attach-plus').disabled);
    assert(await page.locator('#send').isDisabled());
    assert((await page.locator('#notice').textContent()).includes('Uploading'));
    assert(await page.locator('#conversations-dialog').isDisabled());
    assert(await page.locator('#new-chat-dialog').isDisabled());
    releaseUpload(); await expectChips(1); await idle();
    await page.locator('.attach-remove').click(); await expectChips(0);
    if (fs.existsSync(path.join(root, 'photo.heic'))) {
      await page.locator('#attach-input').setInputFiles(path.join(root, 'photo.heic'));
      await expectChips(1); await idle();
      await until(() => document.querySelector('#attach-preview img')?.naturalWidth > 0);
      await page.locator('#send').click(); await expectChips(0); await idle();
      await until(() => [...document.querySelectorAll('.message.assistant img')].length === 2
        && [...document.querySelectorAll('.message.assistant img')].every((img) => img.naturalWidth > 0));
    }
    for (const viewport of [{ width: 390, height: 500 }, { width: 844, height: 390 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      const send = await page.locator('#send').boundingBox();
      assert(send.y >= 0 && send.y + send.height <= viewport.height, 'composer fits reduced/landscape viewport');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'no horizontal page overflow');
    }
    assert.deepEqual(await page.evaluate(() => window.mediaCspFailures), [], 'same-origin previews pass CSP');
    assert.deepEqual(failures, [], 'no page exceptions or external requests');
    if (screenshots) await page.screenshot({ path: path.join(screenshots, `MEDIA-FIXED-0927-${engine}.png`), fullPage: true, animations: 'disabled' });
    console.log(JSON.stringify({ engine, ok: true, checks: ['photos/videos/files in+out', 'video playback/seek', 'download', 'HEIC preview', 'quick action isolation', 'conversation drafts', 'idempotent retry', 'upload errors and progress', '44px targets', 'CSP', 'reduced and landscape viewport'] }));
  } finally { await browser.close(); }
}
(async () => {
  await run('webkit', webkit);
  await run('chromium', chromium);
})().catch((error) => { console.error(error.stack); process.exitCode = 1; });
