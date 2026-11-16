"""Exercise the web trial flow in JavaScript without network calls."""

import shutil
import subprocess
import unittest

from terrainweave.paths import asset_path


@unittest.skipUnless(shutil.which("node"), "Node.js is optional")
class HumanTestFrontendTests(unittest.TestCase):
    def test_trial_error_recovery_and_retry_preserve_original_answer(self) -> None:
        script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map(), listeners = new Map(), frames = [], requests = [];
let now = 700;
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    value: id === 'exposure' ? '500' : '',
    classList: { toggle() {} }, setAttribute() {}, replaceChildren() {}, focus() {},
    removeAttribute(key) { delete this[key]; },
  });
  return elements.get(id);
}
const document = {
  documentElement: {}, getElementById: element, createElement: () => ({}),
  addEventListener(event, callback) { listeners.set(event, callback); },
};
const context = vm.createContext({
  document, crypto: { randomUUID: () => 'test-session' }, AbortController, setTimeout, clearTimeout,
  performance: { now: () => now },
  requestAnimationFrame(callback) { frames.push(callback); },
});
const html = fs.readFileSync(process.argv[1], 'utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
function setFetch(status, json) {
  context.fetch = async (url, request) => {
    requests.push([url, request.body]);
    return { ok: status === 200, status, json: async () => json };
  };
}
(async () => {
  element('language').onchange({target: {value: 'it'}});
  assert.equal(document.documentElement.lang, 'it');
  assert.equal(element('begin').disabled, true);
  element('agree').checked = true;
  element('agree').onchange();
  setFetch(500);
  await element('begin').onclick();
  assert.match(element('intro-error').textContent, /Impossibile caricare il test/);
  assert.equal(element('begin').disabled, false);
  setFetch(200, {trial_set_id: 'test-set', trials: [{trial_id: 'trial_0000', image: 'one.jpg'}]});
  await element('begin').onclick();
  assert.equal(element('test').hidden, false);
  assert.equal(element('progress-label').textContent, 'Prova 1 di 1');

  element('start').onclick();
  assert.equal(element('exposure').disabled, true);
  element('scene').onerror();
  assert.equal(element('start').disabled, false);

  element('start').onclick();
  await element('scene').onload();
  frames.shift()(0);
  frames.shift()(100);
  document.hidden = true;
  listeners.get('visibilitychange')();
  frames.shift()(200);
  assert.equal(element('answers').hidden, true);
  assert.equal(element('start').disabled, false);

  document.hidden = false;
  element('start').onclick();
  await element('scene').onload();
  frames.shift()(0);
  frames.shift()(100);
  element('exposure').value = '100';
  await element('yes').onclick();
  assert.equal(requests.length, 2, 'No answer during exposure');
  frames.shift()(599);
  assert.equal(element('answers').hidden, true);
  frames.shift()(600);
  assert.equal(element('answers').hidden, false);

  setFetch(500);
  await element('yes').onclick();
  const sent = requests.at(-1)[1];
  assert.deepEqual(JSON.parse(sent), {
    session_id: 'test-session', language: 'it', trial_set_id: 'test-set', trial_id: 'trial_0000',
    exposure_ms: 500, detected: 'yes', latency_ms: 600, confidence: '',
  });
  assert.equal(element('progress').value, 0);
  assert.equal(element('answers').hidden, true);
  assert.equal(element('save-controls').hidden, false);
  now = 5000;
  setFetch(200);
  await element('retry').onclick();
  assert.equal(requests.at(-1)[1], sent);
  assert.equal(element('done').hidden, false);
  assert.equal(element('progress').value, 1);

  setFetch(409);
  await vm.runInContext("pending={}; saveAnswer()", context);
  assert.equal(element('reload-controls').hidden, false);
  assert.equal(element('save-controls').hidden, true);
  assert.match(element('status').textContent, /Ricarica la pagina/);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            [shutil.which("node"), "-e", script, str(asset_path("human_test/index.html"))],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
