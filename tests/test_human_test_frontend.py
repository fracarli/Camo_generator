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
const context = vm.createContext({
  document: { getElementById(id) {
    if (!elements.has(id)) elements.set(id, {value: id === 'exposure' ? '500' : '', style: {}, hidden: false});
    return elements.get(id);
  }},
  crypto: { randomUUID: () => 'test-session' },
  performance: { now: () => 1000 },
  fetch: async () => ({ok: false, status: 500}),
  clearTimeout() {}, requestAnimationFrame() {}, console,
});
vm.runInContext(source, context);
vm.runInContext("order=[{trial_id:'trial_0000',image:'/images/trial_0000.jpg'}];waiting=true;shownAt=0", context);
(async () => {
  await vm.runInContext("answer('yes')", context);
  assert.equal(vm.runInContext('index', context), 0, 'An HTTP error must not advance the trial');
  assert.equal(vm.runInContext('waiting', context), true);
  context.fetch = async () => ({ok: true, status: 200});
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
