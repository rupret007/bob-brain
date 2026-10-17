#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(require("node:path").join(__dirname, "static/action-history.js"), "utf8");
const actionContext = vm.createContext({
  window: { setTimeout: (fn) => fn() },
  module: { exports: {} },
  document: { activeElement: null },
});
vm.runInContext(source, actionContext);
const ActionHistory = actionContext.module.exports;

function assistant(overrides) {
  return { role: "assistant", status: "done", id: overrides.id || "msg-" + Math.random().toString(16).slice(2, 8), ...overrides };
}

test("structured local-task receipt renders verbatim without inferred success", () => {
  const messages = [
    assistant({
      id: "msg-1",
      action_receipt: {
        kind: "action.receipt",
        provider: "local",
        type: "task.create",
        timestamp: "2025-01-15T10:00:00Z",
        receipt: { status: "ok", task_id: "t-7", title: "Buy milk" },
      },
    }),
  ];
  const { entries, total } = ActionHistory.extractActionReceipts(messages);
  assert.equal(total, 1);
  assert.equal(entries.length, 1);
  assert.equal(entries[0].provider, "local");
  assert.equal(entries[0].type, "task.create");
  assert.equal(entries[0].timestamp, "2025-01-15T10:00:00Z");
  const body = entries[0].receiptBody;
  assert.match(body, /status: ok/);
  assert.match(body, /task_id: t-7/);
  assert.match(body, /title: Buy milk/);
  assert.equal(entries[0].outcomeLabel, "ok");
  const rendered = ActionHistory.outcomeLine(entries[0]);
  assert.equal(rendered, "Outcome: ok");
  for (const banned of ["success", "✅", "done", "completed"]) {
    assert.ok(!body.toLowerCase().includes(banned) && !rendered.toLowerCase().includes(banned), banned);
  }
});

test("missing structured outcome shows Outcome: unknown", () => {
  const messages = [
    assistant({
      content: "Looks like it worked.",
      action_receipt: {
        kind: "action.receipt",
        provider: "local",
        type: "task.create",
        receipt: { task_id: "t-1" },
      },
    }),
  ];
  const { entries } = ActionHistory.extractActionReceipts(messages);
  assert.equal(entries.length, 1);
  assert.equal(ActionHistory.outcomeLine(entries[0]), "Outcome: unknown");
  assert.equal(entries[0].timestamp, null);
});

test("transport status done does not upgrade failed receipt", () => {
  const messages = [
    assistant({
      status: "done",
      action_receipt: {
        provider: "calendar",
        type: "event.create",
        receipt: { status: "failed", error: "permission_denied" },
      },
    }),
  ];
  const { entries } = ActionHistory.extractActionReceipts(messages);
  assert.equal(entries[0].outcomeLabel, "failed");
  assert.match(entries[0].receiptBody, /error: permission_denied/);
  assert.notEqual(ActionHistory.outcomeLine(entries[0]).toLowerCase(), "outcome: success");
});

test("XSS payload stays literal in receipt body formatting", () => {
  const payload = '<img src=x onerror=alert(1)><script>alert(\'xss\')</script>&"\'<';
  const body = ActionHistory.formatReceiptPayload(payload);
  assert.equal(body, payload);
  const escaped = ActionHistory.escapeHtml(body);
  assert.match(escaped, /&lt;img/);
  assert.match(escaped, /&lt;script/);
});

test("secret sentinel is not required for structural assertions", () => {
  const SENTINEL = "SECRET-SENTINEL-9f8e7d";
  const logs = [];
  const originalLog = console.log;
  console.log = (...args) => logs.push(args.join(" "));
  try {
    const messages = [
      assistant({
        action_receipt: {
          provider: "local",
          type: "task.create",
          receipt: { note: SENTINEL },
        },
      }),
    ];
    const { entries } = ActionHistory.extractActionReceipts(messages);
    assert.equal(entries.length, 1);
    assert.ok(entries[0].receiptBody.length >= 10);
    assert.match(entries[0].receiptBody, /note:/);
    const dump = JSON.stringify({ count: entries.length, hasBody: Boolean(entries[0].receiptBody) });
    assert.ok(!dump.includes("SECRET"));
  } finally {
    console.log = originalLog;
  }
  assert.ok(!logs.some((line) => line.includes("SECRET-SENTINEL")));
});

test("cross-chat extraction stays scoped to supplied messages only", () => {
  const chatA = [
    assistant({ id: "a1", provider: "reminders", content: "Reminder saved: stretch — unique-A" }),
    assistant({ id: "a2", provider: "calendar", content: "Calendar event — unique-A2" }),
  ];
  const chatB = [
    assistant({ id: "b1", provider: "reminders", content: "Reminder saved: water — unique-B" }),
  ];
  const a = ActionHistory.extractActionReceipts(chatA);
  const b = ActionHistory.extractActionReceipts(chatB);
  assert.equal(a.total, 2);
  assert.equal(b.total, 1);
  assert.ok(a.entries.every((e) => e.receiptBody.includes("unique-A")));
  assert.ok(!b.entries.some((e) => e.receiptBody.includes("unique-A")));
});

test("caps at fifty newest entries without fabricating extras", () => {
  const messages = [];
  for (let i = 0; i < 75; i += 1) {
    messages.push(
      assistant({
        id: `m-${i}`,
        created_at: 1_700_000_000 + i,
        provider: "reminders",
        content: `Reminder ${i}`,
      }),
    );
  }
  const { entries, total } = ActionHistory.extractActionReceipts(messages);
  assert.equal(total, 75);
  assert.equal(entries.length, ActionHistory.MAX_ENTRIES);
  assert.equal(entries[0].receiptBody, "Reminder 74");
  assert.equal(entries[entries.length - 1].receiptBody, "Reminder 25");
});

test("empty conversation yields zero entries", () => {
  const { entries, total } = ActionHistory.extractActionReceipts([]);
  assert.equal(total, 0);
  assert.equal(entries.length, 0);
});

test("hold-blocked and no-explicit-yes receipts stay verbatim without send controls", () => {
  const messages = [
    assistant({
      action_receipt: {
        provider: "texting",
        type: "text.send",
        receipt: { status: "blocked", reason: "hold", recipient: "alice@example.com" },
      },
    }),
    assistant({
      action_receipt: {
        provider: "texting",
        type: "text.send",
        receipt: { status: "blocked", reason: "no_explicit_yes" },
      },
    }),
  ];
  const { entries } = ActionHistory.extractActionReceipts(messages);
  assert.equal(entries.length, 2);
  assert.match(entries[0].receiptBody, /reason: hold/);
  assert.match(entries[1].receiptBody, /reason: no_explicit_yes/);
  assert.notEqual(entries[0].outcomeLabel, "delivered");
});

test("duplicate request ids produce separate entries", () => {
  const duplicate = {
    provider: "local-tasks",
    content: "Local draft; no file changed",
    request_id: "req-dup",
  };
  const messages = [
    assistant({ ...duplicate, id: "one", created_at: 10 }),
    assistant({ ...duplicate, id: "two", created_at: 20 }),
  ];
  const { entries, total } = ActionHistory.extractActionReceipts(messages);
  assert.equal(total, 2);
  assert.equal(entries[0].sourceMessageId, "two");
  assert.equal(entries[1].sourceMessageId, "one");
});

test("unconfirmed delivery uses structured texting receipt", () => {
  const messages = [
    assistant({
      texting_receipt: {
        type: "text.send",
        timestamp: "2025-02-01T12:00:00Z",
        receipt: { state: "submitted", deliveryProtocol: 1 },
      },
    }),
  ];
  const { entries } = ActionHistory.extractActionReceipts(messages);
  assert.equal(entries.length, 1);
  assert.equal(entries[0].provider, "texting");
  assert.equal(entries[0].outcomeLabel, "submitted");
});

test("keyboard navigation moves across jump links", () => {
  class EL {
    constructor(tag) {
      this.tagName = tag.toUpperCase();
      this.className = "";
      this.dataset = {};
      this.children = [];
      this.parent = null;
      this.textContent = "";
      this.tabIndex = 0;
      this.focused = false;
    }
    append(...nodes) {
      for (const node of nodes) {
        node.parent = this;
        this.children.push(node);
      }
    }
    querySelectorAll(sel) {
      const out = [];
      const walk = (node) => {
        if (node.className && sel === ".action-history-jump" && node.className.includes("action-history-jump")) out.push(node);
        for (const child of node.children || []) walk(child);
      };
      walk(this);
      return out;
    }
    closest() { return null; }
    focus() { this.focused = true; }
  }
  const list = new EL("div");
  for (let i = 0; i < 3; i += 1) {
    const btn = new EL("button");
    btn.className = "action-history-jump";
    btn.dataset.messageId = `msg-${i}`;
    list.append(btn);
  }
  const links = list.querySelectorAll(".action-history-jump");
  global.document = { activeElement: links[0] };
  const event = { key: "ArrowDown", preventDefault() {} };
  ActionHistory.handleListKeydown(event, list);
  assert.equal(links[1].focused, true);
});

test("jump highlights the target message element", () => {
  const target = {
    dataset: { messageId: "msg-42" },
    classList: { add() {}, remove() {} },
    scrollIntoView() {},
  };
  const root = { querySelectorAll: () => [target] };
  assert.equal(ActionHistory.jumpToMessage("msg-42", root), true);
});
