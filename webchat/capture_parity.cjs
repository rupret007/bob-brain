/* Authenticate in memory and verify the actual public release, including Jobs. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
const [root, url, sha, screenshot, output] = process.argv.slice(2);
const digest = value => crypto.createHash('sha256').update(value).digest('hex');
(async () => {
  const browser = await chromium.launch({headless: true,
    ...(process.env.BOB_CHROMIUM_PATH ? {executablePath: process.env.BOB_CHROMIUM_PATH} : {})});
  try {
    const context = await browser.newContext({viewport: {width: 390, height: 844}, deviceScaleFactor: 2,
      isMobile: true, hasTouch: true, colorScheme: 'dark'});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url + '/login');
    await page.locator('#password').fill(fs.readFileSync(path.join(root, 'conductor/webchat/.password'), 'utf8').trim());
    await page.locator('#login-form button').click();
    await page.waitForURL(url + '/');
    const index = await context.request.get(url + '/');
    assert.match(index.headers()['cache-control'], /no-cache/);
    assert.match(index.headers()['cache-control'], /no-store/);
    const html = await index.text();
    const version = await (await context.request.get(url + '/api/version')).json();
    assert.equal(version.sha, sha);
    assert((await page.locator('#build-info').innerText()).includes(sha.slice(0, 7)));
    assert((await page.locator('#build-info').innerText()).includes(version.built_at));
    const assets = {};
    const names = ['app.js', 'style.css', 'manifest.webmanifest'];
    if (html.includes('/voice.js')) names.push('voice.js');
    for (const name of names) {
      const route = '/' + name + '?v=' + sha.slice(0, 7);
      assert(html.includes(route), 'Asset URL lacks deployed SHA: ' + name);
      const response = await context.request.get(url + route);
      assert.equal(response.status(), 200);
      const served = digest(await response.body());
      assert.equal(served, digest(fs.readFileSync(path.join(__dirname, 'static', name))));
      assets[name] = served;
    }
    if (names.includes('voice.js')) {
      const response = await context.request.get(url + '/voice-capture.js');
      assert.equal(response.status(), 200);
      assets['voice-capture.js'] = digest(await response.body());
      assert.equal(assets['voice-capture.js'], digest(fs.readFileSync(path.join(__dirname, 'static/voice-capture.js'))));
    }
    const activity = page.waitForResponse(response => new URL(response.url()).pathname === '/api/jobs/activity');
    await page.locator('[data-bottom="ops"]').click();
    const jobs = await (await activity).json();
    await page.locator('#view-ops:not([hidden])').waitFor();
    await page.waitForFunction(() => !document.getElementById('jobs-notice').textContent.includes('Checking'));
    assert(jobs.dispatch && typeof jobs.dispatch.paused === 'boolean');
    if (jobs.dispatch.mode === 'solo') {
      await page.locator('#jobs-dispatch').getByText(/Solo mode: additional workers and council are paused/).waitFor();
    } else if (jobs.dispatch.paused) {
      await page.locator('#jobs-dispatch').getByText(/Automatic dispatch is paused/).waitFor();
    }
    if (jobs.recently_finished.some(row => row.source === 'lane_observation')) {
      await page.locator('#finished-jobs').getByText('Outcome unverified', {exact: true}).first().waitFor();
    }
    if (jobs.working.length) {
      assert(await page.locator('.job-card').count() > 0);
      assert.equal(await page.locator('#jobs-empty').isVisible(), false);
    }
    const layouts = [];
    const tabs = html.includes('composer-dock') ? ['chat', 'ops', 'song', 'lanes', 'settings'] : ['ops'];
    for (const width of [320, 390, 430, 900]) {
      await page.setViewportSize({width, height: 844});
      for (const tab of tabs) {
      await page.locator(`[data-bottom="${tab}"]`).click();
      await page.locator(`[data-view="${tab}"]:not([hidden])`).waitFor();
      const metrics = await page.evaluate(() => ({viewport: innerWidth, document: document.documentElement.scrollWidth}));
      assert(metrics.document <= width, tab + ' overflows at ' + width);
      layouts.push({...metrics, tab});
      }
    }
    await page.locator('[data-bottom="ops"]').click();
    await page.setViewportSize({width: 390, height: 844});
    await page.screenshot({path: screenshot, animations: 'disabled'});
    assert.deepEqual(errors, []);
    fs.writeFileSync(output, JSON.stringify({pass_check: true, url, version, assets, layouts,
      working_count: jobs.working.length, dispatch: jobs.dispatch,
      recent_outcomes: jobs.recently_finished.map(row => row.state), screenshot, page_errors: errors}, null, 2) + '\n');
    console.log('Jobs screenshot and public build/assets verified: ' + screenshot);
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
