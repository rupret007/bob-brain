// Actual UI receipt code, deterministic animation frames and transport outcomes.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const source = fs.readFileSync(new URL('static/app.js', import.meta.url), 'utf8');
const start = source.indexOf('  const replyReceiptAttempts =');
const end = source.indexOf('  function render(conversation)', start);
assert(start > 0 && end > start);
function fixture(count = 1) {
  const messages = Array.from({length: count}, (_, i) => ({id: String(i),
    reply_delivery: {id: 'web:' + i, sha256: 'hash:' + i}}));
  const conversation = {id: 'chat-one', messages};
  const articles = messages.map(m => ({dataset: {messageId: m.id, replyDeliveryId: m.reply_delivery.id},
    getBoundingClientRect: () => ({top: 20, bottom: 60, width: 100, height: 40})}));
  const calls = [], frames = [], listeners = {};
  const panel = {children: articles, getBoundingClientRect: () => ({top: 10, bottom: 500}),
    addEventListener: (name, fn) => {listeners[name] = fn;}};
  const context = vm.createContext({current: conversation.id, innerHeight: 600,
    document: {visibilityState: 'visible', addEventListener: (name, fn) => {listeners[name] = fn;}},
    $: () => panel, requestAnimationFrame: fn => frames.push(fn),
    api: (url, data) => {calls.push({url, data}); return Promise.reject(new Error('response lost after commit'));}});
  vm.runInContext(source.slice(start, end), context);
  return {conversation, context, panel, articles, calls, listeners,
    observe: () => context.acknowledgeVisibleReplies(conversation),
    flush: () => {while (frames.length) frames.shift()();}};
}

test('a lost observation response never retries messages or the observation in the same page', async () => {
  const f = fixture();
  for (let i = 0; i < 5; i++) {f.observe(); f.flush();}
  await Promise.resolve();
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].url, '/api/reply-receipts');
  assert.equal(f.calls[0].data.conversation_id, 'chat-one');
  assert.equal(f.calls[0].data.receipts[0].id, 'web:0');
  // A reload may repeat the observation; HTTP tests prove it is idempotent.
  const reloaded = fixture(); reloaded.observe(); reloaded.flush();
  assert.equal(reloaded.calls[0].data.receipts[0].id, 'web:0');
});

test('hidden, offscreen, switched and stale DOM rows cannot be acknowledged', () => {
  for (const mutate of [
    f => {f.context.document.visibilityState = 'hidden';},
    f => {f.context.current = 'another-chat';},
    f => {f.articles[0].dataset.replyDeliveryId = 'older-body';},
    f => {f.articles[0].getBoundingClientRect = () => ({top: 601, bottom: 650, width: 100, height: 49});},
    f => {f.articles[0].getBoundingClientRect = () => ({top: -100, bottom: -1, width: 100, height: 99});},
    f => {f.articles[0].getBoundingClientRect = () => ({top: 20, bottom: 60, width: 0, height: 0});},
  ]) {const f = fixture(); f.observe(); mutate(f); f.flush(); assert.equal(f.calls.length, 0);}
});

test('receipt batches stay bounded and changed text versions get their own observation', () => {
  const f = fixture(35); f.observe(); f.flush(); f.observe(); f.flush();
  assert.deepEqual(f.calls.map(c => c.data.receipts.length), [32, 3]);
  f.conversation.messages[0].reply_delivery = {id: 'web:0:edited', sha256: 'edited-hash'};
  f.articles[0].dataset.replyDeliveryId = 'web:0:edited';
  f.observe(); f.flush();
  assert.equal(f.calls.length, 3);
  assert.equal(f.calls[2].data.receipts[0].sha256, 'edited-hash');
});
