/* Authenticated owner-relay UI; private fixture only, no external services. */
const fs = require('node:fs');
const assert = require('node:assert/strict');
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  const origin = new URL(config.url);
  assert.equal(origin.hostname, '127.0.0.1');
  assert(!['8787', '1234', '4315', '4316'].includes(origin.port));
  const results = [];
  for (const engine of ['chromium', 'webkit']) {
    const browser = await playwright[engine].launch({headless: true});
    try {
      const context = await browser.newContext({viewport: {width: 390, height: 844}, acceptDownloads: true});
      const external = [], errors = [], mutations = [];
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === origin.origin) return route.continue();
        external.push(route.request().url()); return route.abort();
      });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(config.url + '/login');
      await page.locator('#password').fill(config.password);
      await page.locator('#login-form button').click();
      await page.waitForURL(config.url + '/');
      await page.locator('#message:enabled').waitFor();
      page.on('request', req => { if (req.method() !== 'GET') mutations.push(new URL(req.url()).pathname); });
      const downloadLink = page.getByRole('link', {name: 'Download handoff', exact: true}).first();
      await downloadLink.waitFor();
      const [download] = await Promise.all([page.waitForEvent('download'), downloadLink.click()]);
      const body = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
      assert.equal(body.handoff.handoff_id, config.handoff_id);
      assert.equal(body.handoff.state, 'prepared');
      assert.equal(body.handoff.receiver.accepted, false);
      const file = {name: 'review.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(config.artifact))};
      const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/project-handoffs/import');
      // File selection is the only owner-authored mutation in this fixture.
      await page.locator('#messages input[type=file]').first().setInputFiles(file);
      assert.equal((await response).status(), 200);
      const returned = page.getByRole('link', {name: 'Download returned review', exact: true}).first();
      await returned.waitFor();
      const [reviewDownload] = await Promise.all([page.waitForEvent('download'), returned.click()]);
      const saved = JSON.parse(fs.readFileSync(await reviewDownload.path(), 'utf8'));
      assert.equal(saved.artifact.report, config.artifact.report);
      assert.equal(saved.receipt.receiver_identity_verified, false);
      assert.equal(saved.receipt.execution_started, false);
      assert(!await page.locator('#messages img[src="x"]').count());
      assert.deepEqual(external, []); assert.deepEqual(errors, []);
      assert.deepEqual(mutations, ['/api/project-handoffs/import']);
      results.push({engine, pass: true, downloaded: true, imported: true, no_external_requests: true});
    } finally { await browser.close(); }
  }
  process.stdout.write(JSON.stringify({all_pass: true, browsers: results}));
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
