#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "static/reply-playback.js"), "utf8");

function loadReplyPlayback() {
  const context = { module: { exports: {} }, window: {} };
  vm.runInContext(source, vm.createContext(context));
  return context.module.exports;
}

function mockSpeech() {
  const spoken = [];
  const cancelled = [];
  let utterSeq = 0;
  const synthesis = {
    getVoices: () => [{ name: "English fixture", lang: "en-US" }],
    cancel() { cancelled.push(cancelled.length + 1); },
    speak(utter) {
      spoken.push(utter);
      utter._id = ++utterSeq;
      utter._fire = (event) => {
        if (event === "start") utter.onstart?.();
        if (event === "end") utter.onend?.();
        if (event === "error") utter.onerror?.({ error: "synthesis-failed" });
      };
    },
  };
  class Utterance {
    constructor(text) { this.text = text; }
  }
  return { synthesis, Utterance, spoken, cancelled };
}

function makeController(overrides = {}) {
  const ReplyPlayback = loadReplyPlayback();
  const speech = mockSpeech();
  const timers = [];
  const views = [];
  const controller = ReplyPlayback.createController({
    speechSynthesis: speech.synthesis,
    SpeechSynthesisUtterance: speech.Utterance,
    hasSpeech: () => true,
    speechText: (text) => String(text).replace(/\s+/g, " ").trim(),
    ensureSpeechVoices: async () => {},
    isQuietHours: () => false,
    setTimeout: (fn, ms) => {
      const id = { fn, ms, cleared: false };
      timers.push(id);
      return id;
    },
    clearTimeout: (id) => { if (id) id.cleared = true; },
    ...overrides,
  });
  controller.onView = (view) => views.push({ ...view });
  return { ReplyPlayback, controller, speech, timers, views };
}

test("lifecycle: preparing only after speak, speaking only after onstart", async () => {
  const { controller, speech, views } = makeController();
  await controller.start({ rawText: "Hello world", messageId: "m1", source: "message" });
  assert.equal(views.at(-1).state, "preparing");
  assert.equal(views.at(-1).speakingClaimed, false);
  assert.match(views.at(-1).capNotice, /4,000/);
  speech.spoken[0]._fire("start");
  assert.equal(views.at(-1).state, "speaking");
  assert.equal(views.at(-1).speakingClaimed, true);
  speech.spoken[0]._fire("end");
  assert.equal(views.at(-1).state, "idle");
});

test("oversized reply truncates with disclosure", () => {
  const ReplyPlayback = loadReplyPlayback();
  const huge = "a".repeat(4500);
  const built = ReplyPlayback.buildUtteranceText(huge, (t) => t);
  assert.equal(built.text.length, ReplyPlayback.CHAR_CAP);
  assert.equal(built.truncated, true);
  assert.match(ReplyPlayback.capNotice(true), /first 4,000/);
});

test("unsupported API shows fallback without speak", async () => {
  const { controller, speech, views } = makeController({ hasSpeech: () => false });
  const result = await controller.start({ rawText: "Hi", messageId: "m1" });
  assert.equal(result.ok, false);
  assert.equal(speech.spoken.length, 0);
  assert.match(views.find((v) => v.fallback)?.fallback || "", /not supported/);
});

test("onerror moves to failed without automatic retry", async () => {
  const { controller, speech, views } = makeController();
  await controller.start({ rawText: "fail me", messageId: "m9" });
  const before = speech.spoken.length;
  speech.spoken[0]._fire("error");
  assert.equal(views.some((v) => v.state === "failed"), true);
  assert.equal(speech.spoken.length, before, "must not auto-retry speak()");
});

test("stale onstart ignored after rapid switch", async () => {
  const { controller, speech, views } = makeController();
  await controller.start({ rawText: "first", messageId: "m1" });
  const u1 = speech.spoken[0];
  await controller.start({ rawText: "second", messageId: "m2" });
  const u2 = speech.spoken.at(-1);
  u1._fire("start");
  assert.notEqual(views.at(-1).messageId, "m1");
  u2._fire("start");
  assert.equal(views.at(-1).state, "speaking");
  assert.equal(views.at(-1).messageId, "m2");
});

test("stop cancels and ignores late onstart", async () => {
  const { controller, speech } = makeController();
  await controller.start({ rawText: "stop test", messageId: "m3" });
  const utter = speech.spoken[0];
  controller.stop();
  assert.ok(speech.cancelled.length >= 1);
  utter._fire("start");
  assert.equal(controller.getSnapshot().state, "idle");
});

test("conversation change clears playback", async () => {
  const { controller, speech, views } = makeController();
  await controller.start({ rawText: "chat a", messageId: "a1" });
  speech.spoken[0]._fire("start");
  controller.onConversationChange();
  assert.equal(controller.getSnapshot().state, "idle");
  speech.spoken[0]._fire("end");
  assert.equal(views.at(-1).state, "idle");
});

test("logout clears playback", async () => {
  const { controller, speech } = makeController();
  await controller.start({ rawText: "logout", messageId: "x" });
  controller.onLogout();
  assert.equal(controller.getSnapshot().state, "idle");
  assert.ok(speech.cancelled.length >= 1);
});

test("quiet hours block latest manual start only when enforced", async () => {
  const { controller, speech } = makeController({ isQuietHours: () => true });
  const blocked = await controller.start({ rawText: "late", source: "latest", enforceQuietHours: true });
  assert.equal(blocked.reason, "quiet_hours");
  assert.equal(speech.spoken.length, 0);
  assert.equal(controller.getSnapshot().lastSource, null);
  const allowed = await controller.start({ rawText: "late", source: "message", enforceQuietHours: false });
  assert.equal(allowed.ok, true);
  assert.equal(controller.getSnapshot().lastSource, "message");
});

test("silent no-start timeout fails honestly", async () => {
  const { controller, views, timers } = makeController();
  await controller.start({ rawText: "hang", messageId: "slow" });
  const timer = timers.find((t) => t.ms === 10_000);
  assert.ok(timer);
  timer.fn();
  assert.match(views.find((v) => v.state === "failed")?.fallback || "", /did not start/);
});

test("no network or paid side effects in module", () => {
  assert.doesNotMatch(source, /\bfetch\s*\(/);
  assert.doesNotMatch(source, /api_call|openai|gemini/i);
});

test("stop ignores synchronous cancel error events", async () => {
  const { controller, speech, views } = makeController();
  await controller.start({ rawText: "cancel sync", messageId: "m-sync" });
  speech.spoken[0]._fire("start");
  const synthesis = speech.synthesis;
  const utter = speech.spoken[0];
  synthesis.cancel = function syncCancel() {
    speech.cancelled.push(1);
    utter.onerror?.({ error: "canceled" });
  };
  controller.stop();
  assert.equal(views.some((v) => v.state === "failed"), false);
  assert.equal(controller.getSnapshot().state, "idle");
});

test("missing SpeechSynthesisUtterance is unsupported", async () => {
  const { controller, speech } = makeController({
    hasSpeech: () => true,
    SpeechSynthesisUtterance: null,
  });
  const result = await controller.start({ rawText: "Hi", messageId: "m0" });
  assert.equal(result.reason, "unsupported");
  assert.equal(speech.spoken.length, 0);
});

function makeMountUiDom() {
  const nodes = new Map();
  for (const id of ["reply-playback", "reply-playback-state", "reply-playback-message", "reply-playback-cap", "reply-playback-stop", "speak"]) {
    const el = {
      id,
      hidden: id === "reply-playback",
      classList: { classes: new Set(), toggle(name, on) { if (on) this.classes.add(name); else this.classes.delete(name); }, remove(name) { this.classes.delete(name); } },
      dataset: {},
      textContent: "",
      attributes: new Map(),
      setAttribute(name, value) { this.attributes.set(name, value); },
      getAttribute(name) { return this.attributes.get(name); },
      addEventListener() {},
    };
    nodes.set(id, el);
  }
  return {
    getEl: (id) => nodes.get(id),
    panel: () => nodes.get("reply-playback"),
    speak: () => nodes.get("speak"),
    stop: () => nodes.get("reply-playback-stop"),
  };
}

test("mountUi renders preparing, speaking, failed, stop button, and resets #speak on conversation change, logout, and source switch", async () => {
  const ReplyPlayback = loadReplyPlayback();
  const { controller, speech } = makeController();
  const dom = makeMountUiDom();
  const fallbacks = [];
  ReplyPlayback.mountUi({ getEl: dom.getEl, controller, onFallbackNotice: (msg) => fallbacks.push(msg) });
  await controller.start({ rawText: "Hello", messageId: "m1", source: "latest" });
  assert.equal(dom.panel().hidden, false);
  assert.equal(dom.panel().dataset.state, "preparing");
  assert.equal(dom.stop().hidden, false, "stop visible while preparing");
  assert.equal(dom.speak().getAttribute("aria-pressed"), "true");
  speech.spoken[0]._fire("start");
  assert.equal(dom.panel().dataset.state, "speaking");
  assert.equal(dom.stop().hidden, false);
  await controller.start({ rawText: "Other", messageId: "m2", source: "message" });
  assert.equal(dom.speak().getAttribute("aria-pressed"), "false", "speak clears when message playback supersedes latest");
  speech.spoken.at(-1)._fire("start");
  assert.equal(dom.speak().getAttribute("aria-pressed"), "false");
  speech.spoken.at(-1)._fire("end");
  await controller.start({ rawText: "Latest again", messageId: "m3", source: "latest" });
  speech.spoken.at(-1)._fire("start");
  controller.onConversationChange();
  assert.equal(dom.speak().getAttribute("aria-pressed"), "false");
  assert.equal(dom.panel().hidden, true);
  await controller.start({ rawText: "Logout case", messageId: "m4", source: "latest" });
  speech.spoken.at(-1)._fire("start");
  controller.onLogout();
  assert.equal(dom.speak().getAttribute("aria-pressed"), "false");
  await controller.start({ rawText: "fail", messageId: "m5", source: "message" });
  speech.spoken.at(-1)._fire("error");
  assert.equal(dom.panel().hidden, false, "failed panel stays visible after synchronous idle reset");
  assert.equal(dom.panel().dataset.state, "failed");
  assert.ok(fallbacks.length >= 1);
});
