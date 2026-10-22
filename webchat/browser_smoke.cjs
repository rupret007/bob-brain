/* Optional live browser check. Requires Playwright; never prints auth secrets. */
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");
const evidence = path.join(__dirname, "evidence");
fs.mkdirSync(evidence, { recursive: true, mode: 0o700 });

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BOB_CHROMIUM_PATH ? { executablePath: process.env.BOB_CHROMIUM_PATH } : {}) });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto("http://127.0.0.1:8787/");
    assert(page.url().endsWith("/login"));
    await page.screenshot({ path: path.join(evidence, "login-desktop.png"), fullPage: true });
    await page.locator("#password").fill("wrong-password");
    await page.locator("#login-form button").click();
    await page.waitForFunction(() => document.getElementById("login-error").textContent.includes("did not match"));
    await page.locator("#password").fill(fs.readFileSync(path.join(__dirname, ".password"), "utf8").trim());
    await page.locator("#login-form button").click();
    await page.waitForURL("http://127.0.0.1:8787/");
    await page.waitForFunction(() => document.getElementById("conversations").options.length > 0);
    const cookie = (await context.cookies()).find((item) => item.name === "bob_session");
    assert(cookie.httpOnly && cookie.sameSite === "Strict");
    const checks = [];
    for (const [name, text] of [["status", "STATUS"], ["review", ""], ["jobs", "SCREENS"]]) {
      await page.locator(`[data-report="${name}"]`).click();
      await page.waitForFunction(() => document.getElementById("report-body").textContent !== "Loading…");
      const body = await page.locator("#report-body").textContent();
      assert(body.length > 20 && body.includes(text), name + " report");
      checks.push(name);
      await page.locator("#close-report").click();
    }
    const live = JSON.parse(fs.readFileSync(path.join(evidence, "live-chat.json"), "utf8"));
    await page.locator("#conversations").selectOption(live.conversation_id);
    await page.waitForFunction(() => document.getElementById("messages").textContent.includes("amber sailboat"));
    await page.screenshot({ path: path.join(evidence, "chat-desktop.png"), fullPage: true });
    await page.reload();
    await page.waitForFunction(() => document.getElementById("messages").textContent.includes("amber sailboat"));
    assert.equal(await page.locator("#conversations").inputValue(), live.conversation_id);

    // Serve hostile text to this browser only: verify model/report text never becomes HTML.
    const conversationURL = "**/api/conversations/" + live.conversation_id;
    await page.route(conversationURL, async (route) => {
      const response = await route.fetch();
      const data = await response.json();
      data.messages.push({ id: "xss-fixture", role: "assistant", status: "done", created_at: 1, content: '<img src=x onerror="window.bobXss=true">' });
      await route.fulfill({ response, json: data });
    });
    await page.waitForFunction(() => document.getElementById("messages").textContent.includes("onerror"));
    assert.equal(await page.locator("#messages img").count(), 0);
    assert.equal(await page.evaluate(() => window.bobXss), undefined);
    await page.unroute(conversationURL);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForFunction(() => !document.getElementById("messages").textContent.includes("onerror"));
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: path.join(evidence, "chat-mobile.png"), fullPage: true });
    await page.locator("#message").fill("Browser connection check. Reply only: Bob is ready. Do not run tools or commands.");
    await page.locator("#send").click();
    await page.waitForFunction(() => document.getElementById("messages").textContent.includes("Bob is ready.") && document.getElementById("stop").hidden, null, { timeout: 240000 });
    assert.equal(await page.locator("#message").inputValue(), "");
    await page.locator("#new-chat").click();
    await page.waitForFunction(() => document.getElementById("messages").textContent.includes("What’s on your mind?"));
    await page.locator("#logout").click();
    await page.waitForURL("**/login");
    assert.equal((await context.request.get("http://127.0.0.1:8787/api")).status(), 401);
    assert.deepEqual(errors, []);
    const result = { ok: true, checks: ["login failure/success", "HttpOnly session", ...checks, "saved history/reload", "XSS as plain text", "mobile layout", "real composer/polling reply", "new chat", "logout"], browserErrors: errors };
    fs.writeFileSync(path.join(evidence, "browser.json"), JSON.stringify(result, null, 2) + "\n", { mode: 0o600 });
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.message); process.exitCode = 1; });
