/* Isolated phone browser regressions; no worker or external model is started. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");
const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
assert.match(config.url, /^http:\/\/127\.0\.0\.1:\d+$/);
assert(!config.url.endsWith(":8787"), "Proof must use its private listener");

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BOB_CHROMIUM_PATH ? { executablePath: process.env.BOB_CHROMIUM_PATH } : {}) });
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: "dark", isMobile: true, hasTouch: true });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(config.url + "/login");
    await page.locator("#password").fill(config.password);
    await page.locator("#login-form button").click();
    await page.waitForURL(config.url + "/");
    const refresh = async () => {
      await page.locator('[data-bottom="chat"]').click();
      const response = page.waitForResponse(r => r.url().endsWith("/api/jobs/activity"));
      await page.locator('[data-bottom="ops"]').click();
      return (await response).json();
    };
    const fixture = await refresh();
    await page.waitForFunction(() => document.querySelectorAll(".job-card").length === 2);
    assert.equal(fixture.working.length, 2, "A queue claim and its process wrappers must appear once");
    assert.equal(await page.locator(".is-live .job-dot").count(), 2);
    assert.equal(await page.locator(".finished-job").count(), 5);
    assert.equal(await page.locator("#jobs-details").getAttribute("open"), null);
    assert.equal(await page.locator("#jobs-empty").isVisible(), false);
    for (const poison of ["Handback drill", "abc1234", "R38", "Builder scheduler", "Tick not loaded", "Dashboard age", "Nothing running on screen"]) {
      assert(!(await page.locator("#view-ops").innerText()).includes(poison), poison);
    }
    const link = page.locator(".finished-job a").first();
    assert.equal(await link.getAttribute("href"), "https://github.com/example/repo/pull/12");
    await page.locator(".finished-job button").first().click();
    await page.waitForFunction(() => document.getElementById("report-body").textContent.startsWith("Saved browser fixture result"));
    assert.equal(await page.locator("#report-body img").count(), 0);
    await page.locator("#close-report").click();
    await page.locator("#jobs-details summary").click();
    await refresh();
    assert.equal(await page.locator("#jobs-details").getAttribute("open"), "", "Polling must preserve disclosure state");
    assert((await page.locator("#jobs-detail-body").innerText()).includes("Available"));
    await page.locator("#jobs-details summary").click();
    const layouts = [];
    for (const width of [320, 390, 430, 900]) {
      await page.setViewportSize({ width, height: 844 });
      for (const colorScheme of ["dark", "light"]) {
        await page.emulateMedia({ colorScheme });
        const metrics = await page.locator("#view-ops").evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth,
          documentWidth: document.documentElement.scrollWidth, viewport: innerWidth,
          overflowing: [...el.querySelectorAll(".job-card, .finished-job")].filter(row => row.scrollWidth > row.clientWidth).length }));
        assert(metrics.scrollWidth <= metrics.width && metrics.documentWidth <= width && metrics.overflowing === 0, JSON.stringify(metrics));
        layouts.push({ width, colorScheme, ...metrics });
      }
    }
    fs.writeFileSync(config.mode, "unavailable");
    await refresh();
    await page.waitForFunction(() => document.getElementById("jobs-notice").textContent.includes("could not be checked"));
    assert.equal(await page.locator("#jobs-empty").isVisible(), false);
    assert.equal(await page.locator(".is-live .job-dot").count(), 0);
    fs.writeFileSync(config.mode, "empty");
    await refresh();
    await page.waitForFunction(() => !document.getElementById("jobs-empty").hidden);
    assert.equal(await page.locator("#jobs-empty").innerText(), "Nothing running right now.");
    assert.equal(await page.locator(".job-card").count(), 0);
    await page.route("**/api/jobs/activity", route => route.fulfill({ status: 503, contentType: "application/json", body: '{"error":"offline"}' }));
    await refresh();
    await page.waitForFunction(() => document.getElementById("jobs-notice").textContent === "Live work is unavailable. Retrying…");
    assert.equal(await page.locator("#jobs-empty").isVisible(), false);
    await page.unroute("**/api/jobs/activity");
    fs.writeFileSync(config.mode, "live");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ colorScheme: "dark" });
    const live = await refresh();
    await page.waitForFunction(count => document.querySelectorAll(".job-card").length === count, live.working.length);
    await page.locator(".jobs-scroll").evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: config.screenshot });
    assert.deepEqual(errors, []);
    fs.writeFileSync(config.evidence, JSON.stringify({ layouts, screenshot: { width: 390, height: 844, deviceScaleFactor: 2, source: "live" },
      live, fixture_card_count: fixture.working.length, finished_limit: 5, result_opened: true, empty_and_unavailable_passed: true, page_errors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
