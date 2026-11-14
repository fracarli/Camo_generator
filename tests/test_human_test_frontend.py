"""Execute the response handler as JavaScript without a browser or network."""

import shutil
import subprocess
import unittest

from terrainweave.paths import asset_path


@unittest.skipUnless(shutil.which("node"), "Node.js is optional")
class HumanTestFrontendTests(unittest.TestCase):
    def test_http_failure_keeps_the_trial_available_for_retry(self) -> None:
        script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(process.argv[1], 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
const frames = [];
const context = vm.createContext({
  document: { getElementById(id) {
    if (!elements.has(id)) elements.set(id, {value: id === 'exposure' ? '500' : '', style: {}, hidden: false});
    return elements.get(id);
  }},
  crypto: { randomUUID: () => 'test-session' },
  performance: { now: () => 1000 },
  fetch: async () => ({ok: false, status: 500}),
  requestAnimationFrame(callback) { frames.push(callback); }, console,
});
vm.runInContext(source, context);
vm.runInContext("trialSetId='test-set';order=[{trial_id:'trial_0000'}]", context);
(async () => {
  elements.get('start').onclick();
  assert.equal(elements.get('start').disabled, true);
  assert.equal(elements.get('exposure').disabled, true);
  await elements.get('scene').onload();
  frames.shift()(0);
  frames.shift()(100);
  elements.get('exposure').value = '100';
  await vm.runInContext("answer('yes')", context);
  assert.equal(vm.runInContext('waiting', context), false);
  frames.shift()(200);
  assert.equal(elements.get('answers').hidden, true);
  frames.shift()(600);
  assert.equal(elements.get('answers').hidden, false);
  await vm.runInContext("answer('yes')", context);
  assert.equal(vm.runInContext('index', context), 0, 'An HTTP error must not advance the trial');
  assert.equal(vm.runInContext('waiting', context), true);
  context.fetch = async () => ({ok: false, status: 409});
  await vm.runInContext("answer('yes')", context);
  assert.equal(vm.runInContext('index', context), 0);
  assert.match(elements.get('status').textContent, /Reload the page/);
  assert.equal(vm.runInContext('waiting', context), false);
  vm.runInContext('waiting=true', context);
  context.fetch = async (_url, request) => {
    assert.equal(JSON.parse(request.body).trial_set_id, 'test-set');
    assert.equal(JSON.parse(request.body).exposure_ms, 500);
    return {ok: true, status: 200};
  };
  await vm.runInContext("answer('yes')", context);
  assert.equal(vm.runInContext('index', context), 1);
  assert.equal(vm.runInContext('waiting', context), false);
})().catch(error => {console.error(error); process.exitCode=1;});
"""
        result = subprocess.run(
            [
                shutil.which("node"),
                "-e",
                script,
                str(asset_path("human_test/index.html")),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
