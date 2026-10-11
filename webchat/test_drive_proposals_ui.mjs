// Run the actual composer handler with mocked UI and API; no browser or network.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const source = fs.readFileSync(new URL('static/app.js', import.meta.url), 'utf8');
const block = source.slice(source.indexOf('  function composerMessage('), source.indexOf('  $("attach-plus")'));
function fixture() {
  const elements = Object.fromEntries(['composer', 'message', 'provider-choice', 'notice'].map(id => [id, {
    value: '', style: {}, textContent: '', listeners: {}, focus() {},
    addEventListener(name, fn) { this.listeners[name] = fn; },
  }]));
  elements['provider-choice'].value = 'auto';
  const calls = [];
  let count = 0;
  const context = vm.createContext({
    $: id => elements[id], chatReady: true, pendingAttachments: [], busy: false,
    sending: false, uploading: false, draftRequest: null, current: 'fixture-chat',
    crypto: {randomUUID: () => 'fixture-' + (++count)},
    composerState() {}, renderAttachmentStrip() {}, render() {}, refreshList: async () => {},
    api: (url, data) => new Promise((resolve, reject) => calls.push({url, data, resolve, reject})),
  });
  vm.runInContext(block, context);
  return {context, elements, calls, submit: () => elements.composer.listeners.submit({preventDefault() {}})};
}

test('composer transmits exact multiline replacement including empty and trailing whitespace', async () => {
  for (const replacement of ['  Café\n\tlast line\n\n  ', '', '\n']) {
    const f = fixture();
    const input = 'prepare drive replacement 1FixtureDocument0123456789\n' + replacement;
    f.elements.message.value = input;
    const done = f.submit();
    assert.equal(f.calls[0].url, '/api/messages');
    assert.equal(f.calls[0].data.message, input);
    f.calls[0].resolve({messages: []});
    await done;
    assert.equal(f.elements.message.value, '');
  }
});

test('retry reuses request only for exactly equal replacement bytes', async () => {
  const f = fixture();
  f.elements.message.value = 'prepare drive replacement 1FixtureDocument0123456789\nnew\n';
  let done = f.submit();
  const first = f.calls[0].data.request_id;
  f.calls[0].reject(new Error('fixture retry'));
  await done;
  done = f.submit();
  assert.equal(f.calls[1].data.request_id, first);
  f.calls[1].reject(new Error('fixture retry'));
  await done;
  f.elements.message.value += ' ';
  done = f.submit();
  assert.notEqual(f.calls[2].data.request_id, first);
  f.calls[2].resolve({messages: []});
  await done;
});

test('editing whitespace during a pending submission preserves the new composer value', async () => {
  const f = fixture();
  const input = 'prepare drive replacement 1FixtureDocument0123456789\nnew\n';
  f.elements.message.value = input;
  const done = f.submit();
  f.elements.message.value += ' ';
  f.calls[0].resolve({messages: []});
  await done;
  assert.equal(f.elements.message.value, input + ' ');
});

test('ordinary composer messages retain existing trimming behavior', async () => {
  const f = fixture();
  f.elements.message.value = '  hello  ';
  const done = f.submit();
  assert.equal(f.calls[0].data.message, 'hello');
  f.calls[0].resolve({messages: []});
  await done;
  assert.equal(f.elements.message.value, '');
});
