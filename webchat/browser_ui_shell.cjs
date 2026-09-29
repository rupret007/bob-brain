/* Phone-first shell smoke; never logs passwords. */
const fs = require("node:fs");
const assert = require("node:assert/strict");
const playwright = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");

const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

(async () => {
  for (const engine of ['chromium', 'webkit']) {
  const errors = [];
  const browser = await playwright[engine].launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: "dark", isMobile: true });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(config.url + "/login");
    await page.locator("#password").fill(config.password);
    await page.locator("#login-form button").click();
    await page.waitForURL(config.url + "/");
    await page.locator(".composer-dock").waitFor();
    assert.equal(await page.locator("#attach-plus").count(), 1);
    assert.equal(await page.locator(".waveform i").count(), 5);
    assert.equal(await page.locator('[data-bottom="song"]').count(), 1);
    assert.equal(await page.locator('#message').getAttribute('required'), null);
    for (const width of [320, 390, 430, 900, 1280]) {
      await page.setViewportSize({width,height:844});
      for (const tab of ['chat','ops','song','lanes','settings']) {
        await page.locator(`[data-bottom="${tab}"]`).click();
        await page.locator(`[data-view="${tab}"]:not([hidden])`).waitFor();
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),`${engine} ${tab} overflows at ${width}`);
      }
      await page.locator('[data-bottom="chat"]').click();
      for (const id of ['attach-plus','live-call','send']) {
        const rect = await page.locator('#'+id).boundingBox();
        assert(rect.width >= 44 && rect.height >= 44,`${id} has a small tap target`);
      }
    }
    await page.locator('[data-bottom="ops"]').click();await page.locator('.jobs-page-header').waitFor();
    assert.equal(errors.length, 0, errors.join("; "));
  } finally {
    await browser.close();
  }
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
