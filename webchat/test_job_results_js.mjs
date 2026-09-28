#!/usr/bin/env node
// Exercise the actual renderer and result dialog without a live dispatch.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("static/app.js", import.meta.url), "utf8");
const slice = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
const elements = Object.fromEntries(["report-title", "report-date", "report-body", "report"].map(id => [id, { textContent: "" }]));
let opened = 0, fetched = "", unavailable = false;
elements.report.showModal = () => { opened += 1; };
const context = vm.createContext({
  $: id => elements[id],
  api: async url => {
    fetched = url;
    if (unavailable) throw new Error("offline");
    return { project: "Web Bob", task: "Audit replies", text: "Full report: <img src=x onerror=alert(1)>" };
  },
});
vm.runInContext(slice("  function escapeHtml(", "  function isQuietHoursCt(") +
  slice("  function renderMarkdown(", "  const stored =") +
  slice("  async function showJobResult(", "  function composerState("), context);
const id = "webchat-" + "a".repeat(32), url = "/api/jobs/result?id=" + id;
assert.match(context.renderMarkdown(`[full result](${url})`), new RegExp(`data-job-id="${id}"`));
assert.match(context.renderMarkdown(`[<img src=x>](${url})`), /&lt;img src=x&gt;/);
for (const unsafe of ["javascript:alert(1)", "//evil.example", "/api/jobs/result?id=../../secret", url + "&extra=1"]) {
  assert(!context.renderMarkdown(`[result](${unsafe})`).includes("data-job-id"), unsafe);
}
assert.match(context.renderMarkdown("[PR](https://example.org/pr)"), /<a href="https:\/\/example.org\/pr"/);
await context.showJobResult(url);
assert.equal(opened, 1);
assert.equal(fetched, url);
assert.equal(elements["report-title"].textContent, "Web Bob");
assert.equal(elements["report-body"].textContent, "Full report: <img src=x onerror=alert(1)>");
assert.equal(elements["report-body"].innerHTML, undefined);
unavailable = true;
await context.showJobResult(url);
assert.match(elements["report-body"].textContent, /could not be loaded/);
console.log("job_results_js: OK");
