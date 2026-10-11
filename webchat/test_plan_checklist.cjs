const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const SOURCE_PATH = path.join(__dirname, 'static/plan-checklist.js');
const code = fs.readFileSync(SOURCE_PATH, 'utf8');

function loadModule() {
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(code, context);
  return context.window.PlanChecklist;
}
const PlanChecklist = loadModule();

// --- Minimal fake DOM (createElement/textContent/dataset only; no parser,
// so there is nothing for injected markup to execute against). Mirrors the
// hand-rolled fixtures already used by test_voice_js.cjs for this project. ---
function fakeNode(tag) {
  const node = {
    tag, className: '', dataset: {}, children: [], open: false, type: '',
    _text: '',
    get textContent() { return this._text; },
    set textContent(value) { this._text = String(value); this.children = []; },
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { for (const n of nodes) node.appendChild(n); },
  };
  return node;
}
function fakeDocument() {
  return { createElement: (tag) => fakeNode(tag) };
}
function collect(node, out = []) {
  out.push(node);
  for (const child of node.children) collect(child, out);
  return out;
}
function allText(node) {
  return collect(node).map((n) => n._text).filter(Boolean).join(' | ');
}
function findByClass(node, cls) {
  return collect(node).filter((n) => (n.className || '').split(' ').includes(cls));
}

const NOW = 1_800_000_000; // fixed epoch seconds for deterministic tests

function conversation(messages) {
  return { id: 'conv-fixture', messages };
}

test('source never assigns innerHTML (renders only via textContent/dataset)', () => {
  assert.doesNotMatch(code, /\.innerHTML\s*=/);
});

test('T1: happy path — exact-id matches render completed/running and link to result view', () => {
  const ids = ['webchat-aaaa', 'webchat-bbbb'];
  const plan = {
    id: 'm1', group_id: 'group-1', task_ids: ids,
    dispatch_intent: { goal: 'Ship the thing', subtasks: [{ title: 'Write code', worker: 'codex' }, { title: 'Review it', worker: 'cursor' }] },
    action_card: { tasks: [{ id: ids[0], worker: 'codex', status: 'succeeded' }, { id: ids[1], worker: 'cursor', status: 'running' }] },
  };
  const complete = { group_id: 'group-1', subtasks: [{ id: ids[0], status: 'succeeded', finished_at: NOW - 60 }] };
  const conv = conversation([plan, complete]);
  const jobsData = { checked_at: NOW, working: [{ key: ids[1], state: 'running', elapsed_seconds: 30 }], recently_finished: [] };
  const model = PlanChecklist.buildModel(conv, plan, jobsData, NOW);
  assert.equal(model.available, true);
  assert.equal(model.steps[0].status, 'completed');
  assert.equal(model.steps[0].resultId, ids[0]);
  assert.equal(model.steps[0].stale, false);
  assert.equal(model.steps[1].status, 'running');
  assert.equal(model.steps[1].resultId, null);
  assert.equal(model.steps[1].stale, false);
  const node = PlanChecklist.render(fakeDocument(), model, { openDetails: new Set() });
  const buttons = collect(node).filter((n) => n.tag === 'button');
  assert.equal(buttons.length, 1);
  assert.equal(buttons[0].dataset.jobId, ids[0]);
  assert.doesNotMatch(allText(node), /%|ETA/i);
});

test('T2: steps with no recorded id stay proposed, never fabricated as complete', () => {
  const plan = {
    id: 'm2',
    dispatch_intent: { goal: 'Three part plan', subtasks: [{ title: 'A' }, { title: 'B' }, { title: 'C' }] },
  };
  const conv = conversation([plan]);
  const model = PlanChecklist.buildModel(conv, plan, null, NOW);
  assert.equal(model.steps.length, 3);
  for (const step of model.steps) {
    assert.equal(step.status, 'proposed');
    assert.equal(step.id, null);
    assert.equal(step.resultId, null);
  }
  assert.equal(model.counts.proposed, 3);
});

test('T3 adversarial: same-looking job title under a different id cannot complete the step', () => {
  const plan = {
    id: 'm3', task_ids: ['X1'],
    dispatch_intent: { goal: 'Refactor', subtasks: [{ title: 'Refactor auth', worker: 'codex' }] },
    action_card: { tasks: [{ id: 'X1', status: 'queued' }] },
  };
  const conv = conversation([plan]);
  // A decoy job with the identical title text but a different id must never
  // be attributed to this step — matching is by id only.
  const jobsData = { checked_at: NOW, working: [], recently_finished: [{ key: 'Y1', task: 'Refactor auth', state: 'done', result_url: '/api/jobs/result?id=Y1' }] };
  const model = PlanChecklist.buildModel(conv, plan, jobsData, NOW);
  assert.equal(model.steps[0].status, 'queued');
  assert.equal(model.steps[0].resultId, null);
});

test('T4: missing identifiers omit the checklist with an honest unavailable label', () => {
  const plan = { id: 'm4', dispatch_intent: {} };
  const conv = conversation([plan]);
  const model = PlanChecklist.buildModel(conv, plan, null, NOW);
  assert.equal(model.available, false);
  assert.equal(model.reason, 'identifiers-absent');
  const node = PlanChecklist.render(fakeDocument(), model, {});
  assert.match(node.textContent, /unavailable/i);
  assert.doesNotMatch(node.textContent, /%/);
  assert.equal(node.children.length, 0, 'no partial checklist content, just the label');
});

test('T5a: failed step renders distinctly with its recorded observation time', () => {
  const plan = { id: 'm5a', group_id: 'g5', task_ids: ['f'], dispatch_intent: { goal: 'G', subtasks: [{ title: 'Step f' }] }, action_card: { tasks: [{ id: 'f', status: 'running' }] } };
  const complete = { group_id: 'g5', subtasks: [{ id: 'f', status: 'failed', finished_at: NOW - 10 }] };
  const model = PlanChecklist.buildModel(conversation([plan, complete]), plan, null, NOW);
  assert.equal(model.steps[0].status, 'failed');
  assert.equal(model.steps[0].observedAt, NOW - 10);
  assert.equal(model.steps[0].resultId, 'f');
});

test('T5b: held step renders distinctly, carries its recorded time, and offers no action', () => {
  const plan = {
    id: 'm5b', created_at: NOW - 500, content: 'This request touches a project on hold.',
    blocked_dispatch_intent: { goal: 'G', subtasks: [{ title: 'Step h' }] },
  };
  const model = PlanChecklist.buildModel(conversation([plan]), plan, null, NOW);
  assert.equal(model.state, 'held');
  assert.equal(model.steps[0].status, 'held');
  assert.equal(model.steps[0].observedAt, NOW - 500);
  assert.equal(model.note, 'This request touches a project on hold.');
  const node = PlanChecklist.render(fakeDocument(), model, {});
  assert.equal(collect(node).filter((n) => n.tag === 'button').length, 0, 'a held row has no approve/retry control');
});

test('T5c: queued step with no Jobs snapshot yet is not fabricated as stale', () => {
  const plan = { id: 'm5c', task_ids: ['q'], dispatch_intent: { goal: 'G', subtasks: [{ title: 'Step q' }] }, action_card: { tasks: [{ id: 'q', status: 'queued' }] } };
  const model = PlanChecklist.buildModel(conversation([plan]), plan, null, NOW);
  assert.equal(model.steps[0].status, 'queued');
  assert.equal(model.steps[0].stale, false);
  assert.equal(model.steps[0].observedAt, null);
});

test('T5d: running step whose last Jobs snapshot is old renders stale with that observation time', () => {
  const plan = { id: 'm5d', task_ids: ['s'], dispatch_intent: { goal: 'G', subtasks: [{ title: 'Step s' }] }, action_card: { tasks: [{ id: 's', status: 'running' }] } };
  const jobsData = { checked_at: NOW - 300, working: [{ key: 's', state: 'running', elapsed_seconds: 9999 }], recently_finished: [] };
  const model = PlanChecklist.buildModel(conversation([plan]), plan, jobsData, NOW);
  assert.equal(model.steps[0].status, 'running');
  assert.equal(model.steps[0].stale, true);
  assert.equal(model.steps[0].observedAt, NOW - 300);
});

test('T6: out-of-order refresh preserves per-step expansion, unaffected by status changes', () => {
  const plan = { id: 'm6', task_ids: ['sub-2', 'sub-1'], dispatch_intent: { goal: 'G', subtasks: [{ title: 'One' }, { title: 'Two' }] },
    action_card: { tasks: [{ id: 'sub-2', status: 'running' }, { id: 'sub-1', status: 'queued' }] } };
  const conv = conversation([plan]);
  const firstModel = PlanChecklist.buildModel(conv, plan, null, NOW);
  const firstNode = PlanChecklist.render(fakeDocument(), firstModel, { openDetails: new Set() });
  const firstDetails = collect(firstNode).filter((n) => n.tag === 'details');
  const expandedKey = firstDetails[0].dataset.detailKey;
  const openDetails = new Set([expandedKey]);
  // A later, out-of-order poll flips sub-2 from running to completed.
  const complete = { group_id: undefined };
  plan.action_card.tasks[0].status = 'succeeded';
  const secondModel = PlanChecklist.buildModel(conv, plan, null, NOW + 5);
  const secondNode = PlanChecklist.render(fakeDocument(), secondModel, { openDetails });
  const secondDetails = collect(secondNode).filter((n) => n.tag === 'details');
  assert.equal(secondDetails[0].dataset.detailKey, expandedKey);
  assert.equal(secondDetails[0].open, true, 'the previously expanded step stays expanded');
  assert.equal(secondDetails[1].open, false, 'the other step stays collapsed');
  assert.equal(secondModel.steps[0].status, 'completed');
});

test('T7: a held row cannot be promoted by retrying buildModel with later/claimed-fresh inputs', () => {
  const plan = { id: 'm7', created_at: NOW, content: 'On hold.', blocked_dispatch_intent: { goal: 'G', subtasks: [{ title: 'Step' }] } };
  const conv = conversation([plan]);
  const jobsData = { checked_at: NOW + 1000, working: [{ key: 'anything', state: 'running' }], recently_finished: [{ key: 'anything', state: 'done', result_url: '/x' }] };
  const model = PlanChecklist.buildModel(conv, plan, jobsData, NOW + 1000);
  assert.equal(model.steps[0].status, 'held');
  assert.equal(model.steps[0].resultId, null);
});

test('T8 adversarial: unsafe strings in titles/ids are rendered as inert text only', () => {
  const nasty = '<img src=x onerror=alert(1)>';
  const badId = '<script>bad</script>';
  const plan = { id: 'm8', task_id: badId, dispatch_intent: { goal: nasty, prompt: nasty, worker: nasty },
    action_card: { task_id: badId, state: 'running' } };
  const result = { task_id: badId, task_status: 'succeeded', finished_at: NOW };
  const model = PlanChecklist.buildModel(conversation([plan, result]), plan, null, NOW);
  const node = PlanChecklist.render(fakeDocument(), model, {});
  const titleNode = findByClass(node, 'plan-step-title')[0];
  assert.equal(titleNode.textContent, ' ' + nasty);
  const button = collect(node).find((n) => n.tag === 'button');
  assert.equal(button.dataset.jobId, '<script>bad</script>');
  // The fake DOM has no parser; proving textContent/dataset usage (and the
  // absence of innerHTML in the source, asserted above) is what keeps this safe.
});

test('T9: no fabricated percentage, ETA, or progress-bar framing anywhere in the summary', () => {
  const plan = {
    id: 'm9', group_id: 'g9', task_ids: ['a', 'b', 'c', 'd'],
    dispatch_intent: { goal: 'G', subtasks: [{ title: '1' }, { title: '2' }, { title: '3' }, { title: '4' }] },
    action_card: { tasks: [{ id: 'a', status: 'queued' }, { id: 'b', status: 'running' }, { id: 'c', status: 'queued' }, { id: 'd', status: 'queued' }] },
  };
  const complete = { group_id: 'g9', subtasks: [{ id: 'a', status: 'succeeded', finished_at: NOW }] };
  const model = PlanChecklist.buildModel(conversation([plan, complete]), plan, null, NOW);
  const node = PlanChecklist.render(fakeDocument(), model, {});
  const text = allText(node);
  assert.doesNotMatch(text, /%/);
  assert.doesNotMatch(text, /\bETA\b/i);
  assert.doesNotMatch(text, /\d+\s*\/\s*\d+/);
  assert.match(findByClass(node, 'plan-checklist-summary')[0].textContent, /1 completed/);
});

test('T10: conversation isolation and no secret-like fields ever reach the model or DOM', () => {
  const planA = { id: 'a1', task_ids: ['id-a'], dispatch_intent: { goal: 'Conversation A work', subtasks: [{ title: 'A-step' }] },
    action_card: { tasks: [{ id: 'id-a', status: 'running' }] } };
  const planB = { id: 'b1', task_ids: ['id-b'], dispatch_intent: { goal: 'Conversation B work', subtasks: [{ title: 'B-step', authToken: 'leaked-secret-value' }] },
    action_card: { tasks: [{ id: 'id-b', status: 'queued' }] } };
  const jobsDataWithSecret = { checked_at: NOW, working: [{ key: 'id-a', state: 'running', authToken: 'leaked-secret-value' }], recently_finished: [] };
  const modelA = PlanChecklist.buildModel(conversation([planA]), planA, jobsDataWithSecret, NOW);
  const modelB = PlanChecklist.buildModel(conversation([planB]), planB, jobsDataWithSecret, NOW);
  assert.doesNotMatch(JSON.stringify(modelA), /Conversation B|id-b/);
  assert.doesNotMatch(JSON.stringify(modelB), /Conversation A|id-a/);
  assert.doesNotMatch(JSON.stringify(modelA), /leaked-secret-value/);
  assert.doesNotMatch(JSON.stringify(modelB), /leaked-secret-value/);
  const nodeA = PlanChecklist.render(fakeDocument(), modelA, {});
  assert.doesNotMatch(allText(nodeA), /leaked-secret-value|Conversation B/);
});

test('mismatched task_ids length cannot mis-attribute an id to the wrong step', () => {
  const plan = { id: 'm11', task_ids: ['only-one'], dispatch_intent: { goal: 'G', subtasks: [{ title: 'X' }, { title: 'Y' }] } };
  const model = PlanChecklist.buildModel(conversation([plan]), plan, null, NOW);
  for (const step of model.steps) {
    assert.equal(step.id, null);
    assert.equal(step.status, 'proposed');
  }
});

test('cancelled plan renders distinctly with no result link', () => {
  const plan = { id: 'm12', created_at: NOW, content: 'Cancelled before dispatch.', cancelled_dispatch_intent: { goal: 'G', subtasks: [{ title: 'X' }] } };
  const model = PlanChecklist.buildModel(conversation([plan]), plan, null, NOW);
  assert.equal(model.state, 'cancelled');
  assert.equal(model.steps[0].status, 'cancelled');
  assert.equal(model.steps[0].resultId, null);
});

test('an ordinary message with no dispatch intent produces no model at all (nothing rendered)', () => {
  const message = { id: 'plain', role: 'assistant', content: 'Just a normal reply.' };
  const model = PlanChecklist.buildModel(conversation([message]), message, null, NOW);
  assert.equal(model, null);
});

test('single-task (non-batch) dispatch resolves its terminal status from the standalone result message', () => {
  const plan = { id: 'm13', task_id: 'solo-1', dispatch_intent: { prompt: 'Do one thing', worker: 'codex' }, action_card: { task_id: 'solo-1', state: 'running' } };
  const result = { task_id: 'solo-1', task_status: 'succeeded', finished_at: NOW - 5 };
  const model = PlanChecklist.buildModel(conversation([plan, result]), plan, null, NOW);
  assert.equal(model.steps.length, 1);
  assert.equal(model.steps[0].status, 'completed');
  assert.equal(model.steps[0].resultId, 'solo-1');
  assert.equal(model.steps[0].observedAt, NOW - 5);
});
