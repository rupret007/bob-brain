import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const source = fs.readFileSync(new URL('static/app.js', import.meta.url), 'utf8');
const block = source.slice(source.indexOf('  function connectionRestored()'), source.indexOf('  function init()'));
function fixture() {
  let now = 1000;
  const calls = [], rendered = [], secondary = [], elements = new Map();
  const context = vm.createContext({
    Date: {now: () => now}, Promise, Math,
    chatReady: false, connecting: false, authRedirecting: false, connectFailures: 0, connectAfter: 0,
    current: 'saved-chat', csrf: '', pollFailures: 3, overviewFetchedAt: 0, jobsFetchedAt: 0,
    document: {hidden: false},
    $: id => {
      if (!elements.has(id)) elements.set(id, {textContent: '', scrollTop: 0, scrollHeight: 25,
        setAttribute() {}, removeAttribute() {}, classList: {add() {}, remove() {}}});
      return elements.get(id);
    },
    api: url => new Promise((resolve, reject) => calls.push({url, resolve, reject})),
    refreshList: async () => { await context.api('/api/conversations'); context.current = 'server-chat'; },
    render: value => rendered.push(value), composerState() {},
    refreshJobs: async () => secondary.push('jobs'), refreshOverview: async () => secondary.push('overview'),
    clearJobs() {}, clearOverview() {}, poll: () => secondary.push('poll'),
  });
  vm.runInContext(block, context);
  return {context, calls, rendered, secondary, elements, advance: ms => { now += ms; }};
}
const tick = () => new Promise(resolve => setImmediate(resolve));

for (const stage of ['session', 'list', 'history']) {
  test(`initial ${stage} failure recovers using only reads and enables chat after history`, async () => {
    const f = fixture(), c = f.context;
    const first = c.connectChat();
    if (stage !== 'session') { f.calls.at(-1).resolve({csrf: 'private-fixture'}); await tick(); }
    if (stage === 'history') { f.calls.at(-1).resolve({}); await tick(); }
    f.calls.at(-1).reject(new Error('temporary transport failure'));
    await first;
    assert.equal(c.chatReady, false);
    assert.equal(c.connecting, false);
    assert.equal(f.rendered.length, 0);
    assert.equal(f.secondary.length, 0);
    assert.match(f.elements.get('notice').textContent, /Retrying/);
    const count = f.calls.length;
    await c.connectChat();
    f.advance(4999);
    await c.connectChat();
    assert.equal(f.calls.length, count);
    f.advance(1);
    const retry = c.connectChat();
    f.calls.at(-1).resolve({csrf: 'new-fixture'}); await tick();
    f.calls.at(-1).resolve({}); await tick();
    assert.equal(c.chatReady, false);
    assert.equal(f.calls.at(-1).url, '/api/conversations/server-chat');
    f.calls.at(-1).resolve({id: 'server-chat', messages: []}); await retry;
    assert.equal(c.chatReady, true);
    assert.equal(c.csrf, 'new-fixture');
    assert.equal(c.pollFailures, 0);
    assert.equal(f.elements.get('notice').textContent, '');
    assert.equal(f.rendered.length, 1);
    assert.deepEqual(f.secondary, ['jobs', 'overview']);
    await c.connectChat(true);
    assert.equal(f.calls.length, count + 3);
  });
}

test('repeated failures back off and cap at thirty seconds', async () => {
  const f = fixture();
  for (const wait of [5000, 10000, 20000, 30000, 30000]) {
    const before = f.calls.length;
    const pending = f.context.connectChat();
    f.calls.at(-1).reject(new Error('offline')); await pending;
    f.advance(wait - 1);
    await f.context.connectChat();
    assert.equal(f.calls.length, before + 1);
    f.advance(1);
  }
});

test('online and visibility recovery coalesce while a read is pending', async () => {
  const f = fixture(), c = f.context;
  const pending = c.connectChat();
  for (let i = 0; i < 20; i++) c.refreshAfterReconnect();
  assert.equal(f.calls.length, 1);
  f.calls[0].reject(new Error('offline')); await pending;
  c.refreshAfterReconnect();
  assert.equal(f.calls.length, 2, 'an explicit reconnect wakes backoff');
  f.calls[1].reject(new Error('offline')); await tick();
  c.document.hidden = true;
  c.refreshAfterReconnect();
  assert.equal(f.calls.length, 2);
});

test('login redirect suppresses both automatic retries and reconnect attempts', async () => {
  const f = fixture(), c = f.context;
  const pending = c.connectChat();
  c.authRedirecting = true;
  f.calls[0].reject(new Error('Please log in.')); await pending;
  f.advance(60000);
  await c.connectChat(true);
  c.refreshAfterReconnect();
  assert.equal(f.calls.length, 1);
  assert.equal(c.chatReady, false);
  assert.equal(c.connectFailures, 0);
});

test('a mismatched history cannot enable a remembered conversation', async () => {
  const f = fixture(), c = f.context;
  const pending = c.connectChat();
  f.calls[0].resolve({csrf: 'fixture'}); await tick();
  f.calls[1].resolve({}); await tick();
  f.calls[2].resolve({id: 'wrong-chat', messages: []}); await pending;
  assert.equal(c.chatReady, false);
  assert.equal(f.rendered.length, 0);
});

test('ready reconnects leave initialization alone and refresh live reads', () => {
  const f = fixture();
  f.context.chatReady = true;
  f.context.refreshAfterReconnect();
  assert.equal(f.calls.length, 0);
  assert.deepEqual(f.secondary, ['jobs', 'overview', 'poll']);
});
