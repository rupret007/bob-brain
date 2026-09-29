/* Capture chat + jobs screenshots for UI review; never logs auth secrets. */
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
assert.match(config.url, /^http:\/\/127\.0\.0\.1:\d+$/);
assert(config.password && config.outDir);

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const [label, width, height, mobile] of [
      ["phone", 390, 844, true],
      ["desktop", 1280, 900, false],
    ]) {
      const context = await browser.newContext({
        viewport: { width, height },
        deviceScaleFactor: mobile ? 2 : 1,
        colorScheme: "dark",
        ...(mobile ? { isMobile: true, hasTouch: true } : {}),
      });
      const page = await context.newPage();
      await page.goto(config.url + "/login");
      await page.locator("#password").fill(config.password);
      await page.locator("#login-form button").click();
      await page.waitForURL(config.url + "/");
      await page.locator("#view-chat.active").waitFor();
      await page.screenshot({ path: path.join(config.outDir, `${label}-chat.png`) });
      await page.locator('[data-bottom="ops"]').click();
      await page.locator("#view-ops:not([hidden])").waitFor();
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(config.outDir, `${label}-jobs.png`) });
      await context.close();
    }
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
