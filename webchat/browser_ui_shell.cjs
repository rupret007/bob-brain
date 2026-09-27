/* Phone-first shell smoke; never logs passwords. */
const fs = require("node:fs");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

(async () => {
  const errors = [];
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: "dark", isMobile: true });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(config.url + "/login");
    await page.locator("#password").fill(config.password);
    await page.locator("#login-form button").click();
    await page.waitForURL(config.url + "/");
    await page.locator(".composer-dock").waitFor();
    assert.equal(await page.locator("#attach").count(), 1);
    assert.equal(await page.locator(".waveform i").count(), 5);
    assert.equal(await page.locator('[data-bottom="song"]').count(), 0);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.locator('[data-bottom="ops"]').click();
    await page.locator(".jobs-page-header").waitFor();
    assert.equal(errors.length, 0, errors.join("; "));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
