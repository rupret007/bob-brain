/* iPhone layout evidence for Web Bob (390×844 and 430×932). Never prints secrets. */
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");
const evidence = path.join(__dirname, "evidence", "iphone-deep-assess");
fs.mkdirSync(evidence, { recursive: true, mode: 0o700 });
const layout = [];

async function box(page, selector) {
  const loc = page.locator(selector).first();
  if (!(await loc.count())) return null;
  return loc.boundingBox();
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BOB_CHROMIUM_PATH ? { executablePath: process.env.BOB_CHROMIUM_PATH } : {}),
  });
  const password = fs.readFileSync(path.join(__dirname, ".password"), "utf8").trim();
  for (const [tag, width, height] of [["iphone-14", 390, 844], ["iphone-14-pro-max", 430, 932]]) {
    const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 3 });
    const page = await context.newPage();
    await page.goto("http://127.0.0.1:8787/login");
    await page.locator("#password").fill(password);
    await page.locator("#login-form button").click();
    await page.waitForURL("http://127.0.0.1:8787/");
    await page.locator("#messages").waitFor();
    const vh = height;
    const msg = await box(page, "#messages");
    const metrics = {
      viewport: vh,
      messages_px: msg ? Math.round(msg.height) : 0,
      messages_ratio: msg ? msg.height / vh : 0,
    };
    layout.push({ tag, ...metrics });
    await page.screenshot({ path: path.join(evidence, `${tag}-chat.png`) });
    await page.locator("#message").fill("Reply with exactly: playwright ping");
    await page.locator("#send").click();
    await page.locator(".message.assistant .body").last().waitFor({ state: "visible", timeout: 120000 });
    await page.locator('.bottom-tab[data-bottom="ops"]').click();
    await page.locator("#tools-sheet.open").waitFor();
    await page.screenshot({ path: path.join(evidence, `${tag}-jobs-tab.png`) });
    await page.locator("#close-sheet").click();
    await page.locator("#tools-sheet:not(.open)").waitFor();
    await context.close();
  }
  await browser.close();
  const ok = layout.every((row) => row.messages_ratio >= 0.38);
  fs.writeFileSync(path.join(evidence, "layout-metrics.json"), JSON.stringify({ ok, layout }, null, 2) + "\n");
  console.log(JSON.stringify({ ok, folder: evidence, layout }));
  if (!ok) process.exitCode = 1;
})().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
