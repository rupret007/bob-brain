#!/usr/bin/env node
// Exercise actual product functions with controllable HTTP completion order.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";

const source = fs.readFileSync(new URL("static/app.js", import.meta.url), "utf8");
const slice = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
function fixture() {
  const elements = Object.fromEntries(["report-title", "report-date", "report-body", "report-status", "report", "retry-report", "close-report"].map(id => [id, {
    textContent: "", hidden: false, open: false, listeners: {}, attributes: {},
    addEventListener(name, fn) { this.listeners[name] = fn; },
    setAttribute(name, value) { this.attributes[name] = value; },
  }]));
  elements.report.showModal = () => { elements.report.open = true; };
  elements.report.close = () => { elements.report.open = false; elements.report.listeners.close?.(); };
  const calls = [], timers = new Map();
  const context = vm.createContext({
    $: id => elements[id], AbortController,
    document: {activeElement: null, querySelectorAll: () => []},
    setTimeout: (fn, ms) => { const id = {}; timers.set(id, {fn, ms}); return id; },
    clearTimeout: id => timers.delete(id),
    api: (url, data, signal) => new Promise((resolve, reject) => calls.push({url, data, signal, resolve, reject})),
  });
  vm.runInContext(slice("  function escapeHtml(", "  function isQuietHoursCt(") +
    slice("  function renderMarkdown(", "  const stored =") +
    slice(source.includes("  let jobResultRequest") ? "  let jobResultRequest" : "  async function showJobResult(", "  function mediaKindFromFile("), context);
  return {context, elements, calls, timers, open: (...args) => context.showJobResult(...args)};
}

test("chat result links are escaped and limited to exact local job IDs", () => {
  const {context} = fixture();
  const id = "webchat-" + "a".repeat(32), url = "/api/jobs/result?id=" + id;
  assert.match(context.renderMarkdown(`[full result](${url})`), new RegExp(`data-job-id="${id}"`));
  assert.match(context.renderMarkdown(`[<img src=x>](${url})`), /&lt;img src=x&gt;/);
  for (const unsafe of ["javascript:alert(1)", "//evil.example", "/api/jobs/result?id=../../secret", url + "&extra=1"]) {
    assert(!context.renderMarkdown(`[result](${unsafe})`).includes("data-job-id"), unsafe);
  }
  assert.match(context.renderMarkdown("[PR](https://example.org/pr)"), /<a href="https:\/\/example.org\/pr"/);
});

test("saved report stays literal, opens immediately and finishes its loading state", async () => {
  const f = fixture(), pending = f.open("/api/jobs/result?id=one", "Initial title");
  assert.equal(f.elements.report.open, true);
  f.calls[0].resolve({project: "Web Bob", task: "Audit replies", text: "<img src=x onerror=alert(1)>"});
  await pending;
  assert.equal(f.elements["report-title"].textContent, "Web Bob");
  assert.equal(f.elements["report-body"].textContent, "<img src=x onerror=alert(1)>");
  assert.equal(f.elements["report-body"].innerHTML, undefined);
  assert.equal(f.elements["report-body"].attributes["aria-busy"], "false");
  assert.equal(f.timers.size, 0);
});

for (const outcome of ["resolve", "reject"]) {
  test(`an older ${outcome} cannot replace the newly selected job`, async () => {
    const f = fixture(), first = f.open("/api/jobs/result?id=one");
    const second = f.open("/api/jobs/result?id=two");
    f.calls[1].resolve({project: "Second", task: "New result", text: "Keep this result"});
    await second;
    f.calls[0][outcome](outcome === "resolve" ? {project: "Old", text: "Wrong result"} : new Error("old failure"));
    await first;
    assert.equal(f.elements["report-title"].textContent, "Second");
    assert.equal(f.elements["report-body"].textContent, "Keep this result");
    assert.equal(f.calls[0].signal?.aborted, true);
    assert.equal(f.elements["retry-report"].hidden, true);
  });
}

for (const method of ["button", "escape", "close"]) {
  test(`${method} dismisses and cancels the read; late data is ignored`, async () => {
    const f = fixture(), pending = f.open("/api/jobs/result?id=one");
    if (method === "button") f.elements["close-report"].listeners.click?.();
    if (method === "escape") f.elements.report.listeners.cancel?.();
    f.elements.report.close();
    assert.equal(f.timers.size, 0);
    f.calls[0].resolve({project: "Closed", text: "Late report"});
    await pending;
    assert.equal(f.calls[0].signal?.aborted, true);
    assert.notEqual(f.elements["report-body"].textContent, "Late report");
    assert.equal(f.elements.report.open, false);
    assert.equal(f.timers.size, 0);
  });
}

test("queued close event from the old dialog cannot cancel a newly opened read", async () => {
  const f = fixture(), first = f.open("/api/jobs/result?id=one");
  f.elements["close-report"].listeners.click?.();
  const second = f.open("/api/jobs/result?id=two");
  f.elements.report.listeners.close?.();
  f.calls[1].resolve({text: "Newest"});
  await second;
  f.calls[0].reject(new Error("closed"));
  await first;
  assert.equal(f.calls[1].signal?.aborted, false);
  assert.equal(f.elements["report-body"].textContent, "Newest");
});

test("failed read offers only a manual GET retry for the same result", async () => {
  const f = fixture(), first = f.open("/api/jobs/result?id=one", "First", "Task");
  f.calls[0].reject(new Error("private transport detail"));
  await first;
  assert.equal(f.calls.length, 1);
  assert.equal(f.elements["retry-report"].hidden, false);
  assert.match(f.elements["report-status"].textContent, /could not be loaded/);
  assert(!f.elements["report-status"].textContent.includes("private transport"));
  const retry = f.elements["retry-report"].listeners.click();
  assert.equal(f.calls.length, 2);
  assert.equal(f.calls[1].url, f.calls[0].url);
  assert.equal(f.calls[1].data, undefined);
  assert.equal(f.elements["retry-report"].hidden, true);
  f.calls[1].resolve({text: "Recovered"});
  await retry;
  assert.equal(f.elements["report-body"].textContent, "Recovered");
});

test("an in-flight result keeps the existing 15-second read deadline", async () => {
  const f = fixture(), pending = f.open("/api/jobs/result?id=one");
  const timers = [...f.timers.values()];
  assert.equal(timers.length, 1);
  assert.equal(timers[0].ms, 15000);
  timers[0].fn();
  assert.equal(f.calls[0].signal.aborted, true);
  f.calls[0].reject(new Error("aborted"));
  await pending;
  assert.equal(f.elements["retry-report"].hidden, false);
  assert.equal(f.elements["report-body"].attributes["aria-busy"], "false");
  assert.equal(f.timers.size, 0);
});

test("a response delivered after its deadline cannot appear as a successful read", async () => {
  const f = fixture(), pending = f.open("/api/jobs/result?id=one");
  [...f.timers.values()][0].fn();
  f.calls[0].resolve({text: "Late result"});
  await pending;
  assert.notEqual(f.elements["report-body"].textContent, "Late result");
  assert.equal(f.elements["retry-report"].hidden, false);
  f.elements["close-report"].listeners.click();
  f.elements["retry-report"].listeners.click();
  assert.equal(f.calls.length, 1, "Closing forgets the failed read; no hidden retry remains");
});
