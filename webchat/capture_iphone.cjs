/* iPhone layout evidence for Web Bob (390×844 and 430×932). Never prints secrets. */
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");
const evidence = path.join(__dirname, "evidence", process.env.WEBCHAT_IPHONE_EVIDENCE || "iphone-r8");
fs.mkdirSync(evidence, { recursive: true, mode: 0o700 });
const layout = [];
const tabs = ["chat", "ops", "song", "lanes", "settings"];

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
    page.on("dialog", (dialog) => dialog.accept());
    await page.goto("http://127.0.0.1:8787/login");
    await page.locator("#password").fill(password);
    await page.locator("#login-form button").click();
    await page.waitForURL("http://127.0.0.1:8787/");
    await page.locator("#view-chat.active").waitFor();
    const vh = height;
    const msg = await box(page, "#messages");
    const metrics = {
      viewport: vh,
      messages_px: msg ? Math.round(msg.height) : 0,
      messages_ratio: msg ? msg.height / vh : 0,
    };
    layout.push({ tag, ...metrics });
    await page.screenshot({ path: path.join(evidence, `${tag}-chat.png`) });
    for (const tab of tabs.slice(1)) {
      await page.locator('.bottom-tab[data-bottom="chat"]').click();
      await page.locator("#view-chat.active").waitFor({ timeout: 10_000 });
      await page.locator(`.bottom-tab[data-bottom="${tab}"]`).click();
      await page.locator(`.bottom-tab[data-bottom="${tab}"].active`).waitFor({ timeout: 45_000 });
      await page.locator(`[data-view="${tab}"]:not([hidden])`).waitFor({ timeout: 45_000 });
      await page.screenshot({ path: path.join(evidence, `${tag}-${tab}-tab.png`) });
    }
    await page.locator('.bottom-tab[data-bottom="chat"]').click();
    await page.locator("#view-chat.active").waitFor();
    await context.close();
  }
  await browser.close();
  const ok = layout.every((row) => row.messages_ratio >= 0.75);
  fs.writeFileSync(path.join(evidence, "layout-metrics.json"), JSON.stringify({ ok, layout }, null, 2) + "\n");
  console.log(JSON.stringify({ ok, folder: evidence, layout }));
  if (!ok) process.exitCode = 1;
})().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
