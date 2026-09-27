/* iPhone layout evidence for Web Bob (390×844 and 430×932). Never prints secrets. */
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");
const evidence = path.join(__dirname, "evidence", "iphone-r6");
fs.mkdirSync(evidence, { recursive: true, mode: 0o700 });

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BOB_CHROMIUM_PATH ? { executablePath: process.env.BOB_CHROMIUM_PATH } : {}) });
  const password = fs.readFileSync(path.join(__dirname, ".password"), "utf8").trim();
  for (const [tag, width, height] of [["iphone-14", 390, 844], ["iphone-14-pro-max", 430, 932]]) {
    const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 3 });
    const page = await context.newPage();
    await page.goto("http://127.0.0.1:8787/login");
    await page.locator("#password").fill(password);
    await page.locator("#login-form button").click();
    await page.waitForURL("http://127.0.0.1:8787/");
    await page.waitForFunction(() => document.getElementById("messages"));
    await page.screenshot({ path: path.join(evidence, `${tag}-chat.png`) });
    await page.locator("#open-sheet").click();
    await page.waitForFunction(() => document.getElementById("tools-sheet").classList.contains("open"));
    await page.screenshot({ path: path.join(evidence, `${tag}-sheet.png`) });
    await context.close();
  }
  await browser.close();
  console.log(JSON.stringify({ ok: true, folder: evidence }));
})().catch((error) => { console.error(error.message); process.exitCode = 1; });
