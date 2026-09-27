/* Isolated media UI screenshots — no secrets in stdout. */
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");

function arg(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index === -1 ? fallback : process.argv[index + 1];
}

(async () => {
  const url = arg("--url");
  const password = fs.readFileSync(arg("--password-file"), "utf8").trim();
  const conversationId = arg("--conversation");
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BOB_CHROMIUM_PATH ? { executablePath: process.env.BOB_CHROMIUM_PATH } : {}),
  });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  try {
    await page.goto(url + "/login");
    await page.locator("#password").fill(password);
    await page.locator("#login-form button").click();
    await page.waitForURL(url + "/");
    await page.screenshot({ path: arg("--out-login"), fullPage: true });
    await page.evaluate((id) => {
      localStorage.setItem("bob.conversation", id);
    }, conversationId);
    await page.reload();
    await page.locator(".message.user .message-attachments img").waitFor({ timeout: 60000 });
    await page.screenshot({ path: arg("--out-chat"), fullPage: true });
    const png = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABPmXiEAAAAEklEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
      "base64",
    );
    await page.locator("#attach-input").setInputFiles({
      name: "preview.png",
      mimeType: "image/png",
      buffer: png,
    });
    await page.locator("#attach-preview .attach-chip").waitFor({ timeout: 60000 });
    await page.screenshot({ path: arg("--out-attach"), fullPage: true });
    assert(await page.locator("#attach-preview .attach-chip").count());
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
