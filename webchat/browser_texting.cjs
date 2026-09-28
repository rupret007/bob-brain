/* Browser proof against an explicitly supplied isolated fixture; no live defaults. */
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");

(async () => {
  const config = JSON.parse(fs.readFileSync(0, "utf8"));
  const url = new URL(config.url);
  assert.equal(url.hostname, "127.0.0.1");
  assert(!["8787", "1234", "4315"].includes(url.port), "Refuse known live ports");
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BOB_CHROMIUM_PATH ? { executablePath: process.env.BOB_CHROMIUM_PATH } : {}) });
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, reducedMotion: "reduce" });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    // The browser cannot contact anything except this proof server.
    await context.route("**/*", route => new URL(route.request().url()).origin === url.origin
      ? route.continue() : route.abort());
    await page.goto(config.url + "/login");
    await page.locator("#password").fill(config.password);
    await page.locator("#login-form button").click();
    await page.waitForURL(config.url + "/");
    await page.locator("#send:enabled").waitFor();
    async function say(text) {
      await page.locator("#message").fill(text);
      const response = page.waitForResponse(r => r.url() === config.url + "/api/messages" && r.request().method() === "POST");
      await page.locator("#send").click();
      const result = await response;
      assert.equal(result.status(), 202);
      const data = await result.json();
      await page.locator("#send:enabled").waitFor();
      return data;
    }
    const screenshots = [];
    async function screenshot(name) {
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      assert.equal(overflow, false, "Phone must not scroll sideways");
      const filename = `WEBBOB-TEXTING-0927-${name}.png`;
      await page.screenshot({ path: path.join(config.output, filename), animations: "disabled" });
      screenshots.push(filename);
    }
    await page.getByRole("button", { name: "Texts", exact: true }).click();
    await page.getByText("Recent text threads", { exact: false }).waitFor();
    const summary = await say("summarize texts from Alex Morgan");
    assert(summary.messages.at(-1).content.includes("3 messages, 2 incoming and 1 from you"));
    await screenshot("phone-summary");
    const first = await say("draft reply to Alex Morgan: I’ll bring the charts at 6.");
    const oldDraft = first.messages.at(-1).text_draft;
    const firstCard = page.locator(".text-draft-card").last();
    assert.equal(await firstCard.locator(".text-draft-body").textContent(), oldDraft.body);
    assert((await firstCard.locator(".text-recipient").textContent()).includes("+15550101010"));
    await firstCard.scrollIntoViewIfNeeded();
    await screenshot("phone-draft");
    await firstCard.getByRole("button", { name: "Edit draft", exact: true }).click();
    const editCard = page.locator('.text-draft-card[data-state="editing"]');
    await editCard.waitFor();
    assert.equal(await page.locator(".text-confirmation").count(), 0);
    await editCard.getByLabel("Text body").fill("I’ll bring the charts at 7.");
    await editCard.getByRole("button", { name: "Review new draft" }).click();
    const newCard = page.locator('.text-draft-card[data-state="pending"]');
    await newCard.waitFor();
    const newConfirmation = await newCard.locator(".text-confirmation").textContent();
    assert.notEqual(newConfirmation, oldDraft.confirm_message);
    assert.equal(await newCard.locator(".text-draft-body").textContent(), "I’ll bring the charts at 7.");
    const stale = await say(oldDraft.confirm_message);
    assert(stale.messages.at(-1).content.includes("does not match"));
    await newCard.scrollIntoViewIfNeeded();
    await screenshot("phone-revised");
    // This only fills the composer; a separate chat submission is still necessary.
    const before = await page.locator(".message.user").count();
    await newCard.getByRole("button", { name: "Put confirmation in chat" }).click();
    assert.equal(await page.locator(".message.user").count(), before);
    assert.equal(await page.locator("#message").inputValue(), newConfirmation);
    const result = await say(newConfirmation);
    assert(result.messages.at(-1).content.startsWith("Not sent."));
    await screenshot("phone-not-sent");
    await page.setViewportSize({ width: 1100, height: 1000 });
    await page.locator('.text-draft-card[data-state="confirmed_not_sent"]').scrollIntoViewIfNeeded();
    await screenshot("desktop-confirmed-not-sent");
    await page.reload();
    await page.locator('.text-draft-card[data-state="confirmed_not_sent"]').waitFor();
    assert.equal(await page.locator(".text-confirmation").count(), 0);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ ok: true, synthetic_only: true, screenshots, browser_errors: errors,
      checks: ["login", "thread summary", "exact recipient and body", "edit clears consent",
        "new token after edit", "stale token rejected", "separate chat submission", "honest blocked receipt",
        "reload preserves consumed consent", "no horizontal phone overflow"] }));
    await context.close();
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
