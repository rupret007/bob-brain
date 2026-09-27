/* Optional Playwright check of real saved failover replies and the lanes panel. */
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");
const evidence = path.join(__dirname, "evidence");

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BOB_CHROMIUM_PATH ? { executablePath: process.env.BOB_CHROMIUM_PATH } : {}) });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  try {
    await page.goto("http://127.0.0.1:8787/login");
    await page.locator("#password").fill(fs.readFileSync(path.join(__dirname, ".password"), "utf8").trim());
    await page.locator("#login-form button").click();
    await page.waitForURL("http://127.0.0.1:8787/");
    const result = JSON.parse(fs.readFileSync(path.join(evidence, "failover-live.json"), "utf8"));
    const cid = result.checks.find(c => c.check === "codex_to_cursor").conversation_id;
    await page.waitForFunction(() => document.getElementById("conversations").options.length > 0);
    await page.locator("#conversations").selectOption(cid);
    await page.waitForFunction(() => document.getElementById("messages").textContent.includes("switched to Cursor"));
    await page.locator("#lanes-panel summary").click();
    await page.waitForFunction(() => document.getElementById("lanes").textContent.includes("MiniMax"));
    const lanes = await page.locator("#lanes").innerText();
    assert(lanes.includes("$48") && lanes.includes("Claude") && lanes.includes("explicit choice only"));
    await page.screenshot({ path: path.join(evidence, "failover-desktop.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: path.join(evidence, "failover-mobile.png"), fullPage: true });
    await page.locator("#lanes-panel summary").click();
    await page.locator("#new-chat").click();
    await page.waitForFunction(() => document.getElementById("messages").textContent.includes("What’s on your mind?"));
    await page.locator("#message").fill("Reply exactly: Browser failover check passed.");
    await page.locator("#send").click();
    await page.waitForFunction(() => document.getElementById("messages").textContent.includes("Browser failover check passed.") && document.getElementById("stop").hidden, null, { timeout: 90000 });
    assert.equal(await page.locator("#message").inputValue(), "");
    assert.deepEqual(errors, []);
    const receipt = { ok: true, checks: ["saved failover explanation", "all five lanes", "$48 chat ceiling", "Claude explicit only", "390px mobile layout", "real composer/send/reply"], browserErrors: errors };
    fs.writeFileSync(path.join(evidence, "failover-browser.json"), JSON.stringify(receipt, null, 2) + "\n", { mode: 0o600 });
    console.log(JSON.stringify(receipt));
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
