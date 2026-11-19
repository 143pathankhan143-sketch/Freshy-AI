import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createApp } from './server.js';

async function setup(t, options) {
  const server = createApp(options).listen(0, '127.0.0.1');
  await once(server, 'listening'); t.after(() => new Promise(resolve => server.close(resolve)));
  return messages => fetch(`http://127.0.0.1:${server.address().port}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages }) });
}
const first = { role: 'user', content: 'Photosynthesis kya hai?' };
test('passes previous turns as Gemini context without enabling tools', async t => {
  let payload;
  const post = await setup(t, { key: 'test', request: async (_, options) => {
    payload = JSON.parse(options.body);
    return Response.json({ candidates: [{ content: { parts: [{ text: 'Short answer' }] } }] });
  } });
  const history = [first, { role: 'assistant', content: 'Plants use sunlight.' }, { role: 'user', content: 'Do lines mein batao.' }];
  const res = await post(history);
  assert.deepEqual(await res.json(), { reply: 'Short answer' });
  assert.deepEqual(payload.contents.map(c => c.role), ['user', 'model', 'user']);
  assert.deepEqual(payload.contents.map(c => c.parts[0].text), history.map(m => m.content));
  assert.equal(payload.tools, undefined);
});
test('rejects invalid turns and handles missing configuration', async t => {
  const post = await setup(t, { key: '' });
  for (const messages of [[], [{ ...first, role: 'system' }], [{ ...first, content: ' ' }], [first, first]]) assert.equal((await post(messages)).status, 400);
  assert.equal((await post([first])).status, 503);
});
test('reports upstream quota without exposing raw upstream text', async t => {
  const post = await setup(t, { key: 'test', request: async () => new Response('sensitive detail', { status: 429 }) });
  const res = await post([first]); assert.equal(res.status, 429); assert.doesNotMatch(await res.text(), /sensitive detail/);
});
