/* Isolated phone proof. Primary screenshots use actual private-server responses.
 * Explicit browser fixtures below are regression cases, never screenshot data. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.BOB_PLAYWRIGHT_MODULE || "playwright");
const url = process.env.WEBBOB_TEST_URL;
assert(url && /^http:\/\/127\.0\.0\.1:\d+$/.test(url) && !url.endsWith(":8787"), "Use the isolated proof runner");
const password = fs.readFileSync(process.env.WEBBOB_TEST_PASSWORD_FILE, "utf8").trim();
const output = process.env.WEBBOB_TEST_OUTPUT;
const tabs = { chat: "Chat", ops: "Jobs", song: "Songs", lanes: "Models", settings: "Settings" };
const evidence = { screenshots: [], layouts: [], checks: [], screenshot_data: "Actual isolated server responses; empty private chats/songs, current read-only host activity, unchecked private model health." };
const errors = [];
let browser;

async function ready(page) {
  await page.waitForFunction(() => document.querySelector("#send")?.disabled === false
    && !/Checking|Refreshing/.test(document.querySelector("#jobs-notice").textContent)
    && !/Loading/.test(document.querySelector("#song-summary").textContent));
}
async function tab(page, name) {
  await page.locator(`[data-bottom="${name}"]`).click();
  assert(await page.locator(`#view-${name}`).isVisible());
  await page.waitForTimeout(150); // Let the mobile compositor finish the tab change.
}
async function refresh(page) {
  const jobs = await page.locator("#view-ops").isVisible();
  const response = page.waitForResponse((res) => res.url().includes(jobs ? "/api/jobs/activity" : "/api/overview"));
  await page.locator(jobs ? "#refresh-jobs" : ".main-view:not([hidden]) [data-refresh]").click();
  await response;
  await page.waitForFunction(() => [...document.querySelectorAll("[data-refresh], #refresh-jobs")].every((button) => !button.disabled));
}
async function layout(page, width, name) {
  const metric = await page.evaluate(() => {
    const view = document.querySelector(".main-view:not([hidden])");
    const buttons = [...document.querySelectorAll(".bottom-tab")].map((button) => {
      const rect = button.getBoundingClientRect();
      return { width: rect.width, height: rect.height, bottom: rect.bottom };
    });
    const header = document.querySelector(".top-bar").getBoundingClientRect();
    return { header: { y: header.y, height: header.height }, viewport: innerWidth, document: document.documentElement.scrollWidth,
      view: view.scrollWidth, viewWidth: view.clientWidth, buttons,
      openDetails: view.querySelectorAll("details[open]").length };
  });
  assert(metric.document <= width && metric.view <= metric.viewWidth + 1, `${name} overflows at ${width}`);
  assert(metric.header.y >= 0 && metric.header.height >= 44, `${name} header stays on screen`);
  assert(metric.buttons.every((button) => button.width >= 44 && button.height >= 44 && button.bottom <= 845));
  assert.equal(metric.openDetails, 0, `${name} details start collapsed`);
  evidence.layouts.push({ tab: tabs[name], width, ...metric });
}

(async () => {
  browser = await chromium.launch({ headless: true, args: ["--disable-gpu"],
    ...(process.env.BOB_CHROMIUM_PATH ? { executablePath: process.env.BOB_CHROMIUM_PATH } : {}) });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
    colorScheme: "dark", isMobile: true, hasTouch: true, reducedMotion: "reduce" });
  await context.route("**/*", (route) => {
    assert(route.request().url().startsWith(url + "/"), "Browser must remain on the private listener");
    route.continue();
  });
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(url + "/login");
  await page.locator("#password").fill(password);
  await page.locator("#login-form button").click();
  await page.waitForURL(url + "/");
  await ready(page);
  evidence.actual_jobs = await (await page.request.get(url + "/api/jobs/activity")).json();
  evidence.actual_overview = await (await page.request.get(url + "/api/overview")).json();
  for (const width of [390, 320, 430]) {
    await page.setViewportSize({ width, height: 844 });
    for (const [name, label] of Object.entries(tabs)) {
      await tab(page, name);
      await layout(page, width, name);
      if (width === 390) {
        const filename = `webbob-tab-${label.toLowerCase()}-0927.png`;
        await page.screenshot({ path: path.join(output, filename), animations: "disabled" });
        evidence.screenshots.push(filename);
      }
    }
  }
  evidence.checks.push("All five tabs fit 320, 390 and 430 pixels; navigation targets meet 44 pixels; details start collapsed.");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "light" });
  for (const name of Object.keys(tabs)) { await tab(page, name); await layout(page, 390, name); }
  await page.emulateMedia({ colorScheme: "dark" });
  await tab(page, "settings");
  await page.locator("#provider-choice").selectOption("minimax");
  await page.reload();
  await ready(page);
  assert.equal(await page.locator("#provider-choice").inputValue(), "minimax");
  assert.equal(await page.locator("#attach-plus").count(), 0);
  assert.equal(await page.locator("#conversations").count(), 1);
  evidence.checks.push("Reply preference survives reload; one conversation picker; unfinished attachment control removed.");

  await tab(page, "song");
  assert(await page.locator("#songs-empty").isVisible());
  await page.locator("#song-new").click();
  await page.locator("#song-title").blur();
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(output, "webbob-tab-songs-editor-0927.png"), animations: "disabled" });
  evidence.screenshots.push("webbob-tab-songs-editor-0927.png");
  for (const width of [320, 390, 430]) {
    await page.setViewportSize({ width, height: 844 });
    await layout(page, width, "song");
    await page.locator("#song-audio summary").click();
    assert(await page.locator("#song-upload").isVisible());
    assert(await page.evaluate(() => document.documentElement.scrollWidth === innerWidth));
    await page.locator("#song-audio summary").click();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  evidence.checks.push("Light theme across all tabs and empty song editor/audio controls at all three phone widths.");
  await page.locator("#song-title").fill("Notebook regression");
  await page.locator("#song-lyrics").fill("These are temporary browser test lyrics.");
  const save = page.waitForResponse((res) => res.url().endsWith("/api/song-projects") && res.request().method() === "POST");
  await page.locator("#song-save").click();
  const saved = await (await save).json();
  await page.waitForFunction(() => document.querySelector("#song-notice").textContent === "Song saved." && !document.querySelector("#song-save").disabled);
  assert.equal(await page.locator("#song-picker").inputValue(), saved.id);
  assert.equal(await page.locator("#song-versions li").count(), 1);
  await page.locator("#song-history summary").click();
  assert((await page.locator("#song-versions").innerText()).includes("temporary browser test lyrics"));
  // A prior audio source must not carry into a different song.
  await page.evaluate(() => { const player = document.querySelector("#song-player"); player.src = "/api/audio/prior-recording"; player.hidden = false; });
  await page.locator("#song-new").click();
  assert.equal(await page.locator("#song-player").getAttribute("src"), null);
  assert(await page.locator("#song-history").isHidden());
  await page.locator("#song-picker").selectOption(saved.id);
  await page.waitForFunction(() => document.querySelector("#song-title").value === "Notebook regression" && !document.querySelector("#song-save").disabled);
  await page.locator("#song-lyrics").fill("Keep these unsaved edits.");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.locator('[data-bottom="chat"]').click();
  assert(await page.locator("#view-song").isVisible());
  await page.route("**/api/song-projects", (route) => route.request().method() === "POST"
    ? route.fulfill({ status: 503, json: { error: "Save unavailable." } }) : route.continue());
  await page.locator("#song-save").click();
  await page.waitForFunction(() => document.querySelector("#song-notice").textContent.startsWith("Not saved."));
  assert.equal(await page.locator("#song-lyrics").inputValue(), "Keep these unsaved edits.");
  await page.unroute("**/api/song-projects");
  await page.locator("#song-save").click();
  await page.waitForFunction(() => document.querySelector("#song-notice").textContent === "Song saved." && !document.querySelector("#song-save").disabled);
  evidence.checks.push("Real private song save/load/version history; previous audio and versions cleared on new song; unsaved edits protected; failed save never claims persistence.");

  const fixture = {
    inspection: { processes_available: true, screens_available: true, queue_available: true },
    work: [
      { job_id: "job-a", title: "Review phone layout", worker: "codex", state: "running", elapsed_seconds: 125, pid: 101 },
      { job_id: "job-a", title: "Duplicate row", worker: "codex", state: "running", elapsed_seconds: 125, pid: 101 },
      { screen: "lane-unconfirmed", title: "Open session", state: "unverified" },
    ],
    queued: [{ job_id: "job-a", title: "Duplicate queue row" }, { job_id: "job-b", title: "Check song editor", worker: "cursor" }],
    models: { codex: { state: "ready", usage: {} }, minimax: { state: "cooldown", reason: "rate_limit", retry_at: Date.now() / 1000 + 600, usage: { spent_usd: 0, reserved_usd: .25 } },
      gemini: { state: "unchecked" } },
    automation: { launchd_loaded: false, launchd_files_ok: true },
    live_ops: { now_line: "OLD DASHBOARD", scores: [{ area: "Fake", score: 10 }] },
  };
  const jobsFixture = {
    inspection: fixture.inspection,
    working: [
      { key: "job-a", project: "Web Bob", task: "Review phone layout", models: ["Codex"], state: "running", elapsed_seconds: 125 },
      { key: "job-a", project: "Web Bob", task: "Duplicate row", models: ["Codex"], state: "running", elapsed_seconds: 125 },
      { key: "session-b", project: "WebJam", task: "Review a draft", models: [], state: "unverified", elapsed_seconds: null },
    ],
    recently_finished: [{ key: "finished-a", project: "Web Bob", task: "Saved check", state: "done", finished_at: Date.now() / 1000 - 60 }],
    details: { queued: 1, unconfirmed: 1 },
  };
  await page.route("**/api/overview*", (route) => route.fulfill({ json: { ...fixture, captured_at: new Date().toISOString() } }));
  await page.route("**/api/jobs/activity", (route) => route.fulfill({ json: { ...jobsFixture, checked_at: Date.now() / 1000 } }));
  await tab(page, "ops"); await refresh(page);
  assert.equal(await page.locator(".job-card").count(), 2);
  assert.equal(await page.locator(".finished-job").count(), 1);
  assert(!(await page.locator("#view-ops").innerText()).includes("Duplicate"));
  assert(!(await page.locator("#view-ops").innerText()).includes("OLD DASHBOARD"));
  assert(!(await page.locator("#view-ops").innerText()).includes("job-a"));
  await page.locator("#jobs-details summary").click();
  assert((await page.locator("#jobs-detail-body").innerText()).includes("1 queued"));
  await refresh(page);
  assert.equal(await page.locator("#jobs-details[open]").count(), 1);
  await tab(page, "lanes"); await refresh(page);
  const codex = page.locator(".lane-card").filter({ has: page.locator("h3", { hasText: "Codex" }) });
  assert((await codex.innerText()).includes("In use"));
  const minimax = page.locator(".lane-card").filter({ has: page.locator("h3", { hasText: "MiniMax" }) });
  assert(!(await minimax.innerText()).includes("$"));
  await minimax.locator("summary").click();
  assert((await minimax.innerText()).includes("$0.00"));
  assert((await minimax.innerText()).includes("Usage limit reached"));
  await refresh(page);
  assert.equal(await minimax.locator("details[open]").count(), 1);
  evidence.checks.push("Fixture: duplicate job cards collapse; recent results remain; unconfirmed activity is explicit; IDs stay hidden and costs stay collapsed; details stay open during polling; live activity overrides cached ready state.");

  for (const route of ["**/api/overview*", "**/api/jobs/activity"]) {
    await page.unroute(route);
    await page.route(route, (request) => request.fulfill({ status: 503, json: { error: "Unavailable" } }));
  }
  await refresh(page);
  assert.equal(await page.locator(".lane-card").count(), 0);
  await tab(page, "ops"); await refresh(page);
  assert.equal(await page.locator(".job-card").count(), 0);
  assert.equal(await page.locator(".finished-job").count(), 0);
  assert(await page.locator("#jobs-empty").isHidden());
  for (const route of ["**/api/overview*", "**/api/jobs/activity"]) await page.unroute(route);
  await page.route("**/api/overview*", (route) => route.fulfill({ json: { ...fixture, captured_at: "2020-01-01T00:00:00Z" } }));
  await page.route("**/api/jobs/activity", (route) => route.fulfill({ json: { ...jobsFixture, checked_at: 1 } }));
  await refresh(page);
  assert.equal(await page.locator(".job-card").count(), 0);
  assert((await page.locator("#jobs-notice").textContent()).includes("unavailable"));
  await tab(page, "lanes"); await refresh(page);
  assert.equal(await page.locator(".lane-card").count(), 0);
  for (const route of ["**/api/overview*", "**/api/jobs/activity"]) await page.unroute(route);
  await page.route("**/api/overview*", (route) => route.fulfill({ json: { captured_at: new Date().toISOString(), inspection: fixture.inspection, work: [], queued: [], models: {}, automation: {} } }));
  await page.route("**/api/jobs/activity", (route) => route.fulfill({ json: { checked_at: Date.now() / 1000, inspection: fixture.inspection, working: [], recently_finished: [], details: {} } }));
  await refresh(page);
  assert(await page.locator("#models-empty").isVisible());
  await tab(page, "ops"); await refresh(page);
  assert(await page.locator("#jobs-empty").isVisible());
  evidence.checks.push("Fixture: failures and stale responses clear prior jobs, finished results and model values without claiming no work; successful empty checks show useful empty states.");

  for (const route of ["**/api/overview*", "**/api/jobs/activity"]) await page.unroute(route);
  await page.route("**/api/conversations/*", async (route) => {
    const response = await route.fetch();
    const conversation = await response.json();
    conversation.messages = [{ role: "assistant", content: "A reply for the retry display test.", status: "done", provider: "gemini",
      attempts: [{ provider: "codex", error: "rate_limit" }, { provider: "codex", error: "rate_limit" }] }];
    await route.fulfill({ json: conversation });
  });
  await tab(page, "chat");
  await page.locator(".reply-details").waitFor();
  assert(!(await page.locator("#messages").innerText()).includes("Usage limit reached"));
  await page.locator(".reply-details summary").click();
  assert.equal(await page.locator(".reply-details p").count(), 1);
  assert((await page.locator(".reply-details").innerText()).includes("Codex: Usage limit reached"));
  evidence.checks.push("Fixture: chat retry details are collapsed, deduplicated and translated into plain words.");
  assert.deepEqual(errors, [], "No browser runtime errors");
  evidence.checks.push("No browser runtime errors or external browser requests.");
  await context.close();
  evidence.result = "PASS";
  fs.writeFileSync(path.join(output, "WEBBOB-CLEAN-0927.tabs-evidence.json"), JSON.stringify(evidence, null, 2) + "\n");
  console.log(JSON.stringify({ result: evidence.result, screenshots: evidence.screenshots, layouts: evidence.layouts.length, checks: evidence.checks.length }));
})().catch((error) => { console.error(error.stack); process.exitCode = 1; }).finally(async () => { if (browser) await browser.close(); });
