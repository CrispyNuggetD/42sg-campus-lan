'use strict';
// Untrusted input is Wasm only, with zero imports. vm supplies the CPU timeout;
// it is NOT used as a sandbox for arbitrary JavaScript. Python validates memory
// limits before this process starts and imposes an outer wall-clock deadline.
const fs = require('fs');
const vm = require('vm');
const requests = JSON.parse(fs.readFileSync(0, 'utf8'));
const script = new vm.Script(`
  const module = new WebAssembly.Module(bytes);
  if (WebAssembly.Module.imports(module).length) throw Error('Imports disabled');
  const e = new WebAssembly.Instance(module, {}).exports;
  if (!(e.memory instanceof WebAssembly.Memory) ||
      typeof e.hw_state !== 'function' || typeof e.hw_step !== 'function' ||
      typeof e.hw_config !== 'function') throw Error('Missing SDK exports');
  function words(ptr, length) {
    if (!Number.isInteger(ptr) || ptr < 0 || ptr % 4 ||
        ptr + length * 4 > e.memory.buffer.byteLength) throw Error('Invalid SDK pointer');
    return new Int32Array(e.memory.buffer, ptr, length);
  }
  const attributes = Array.from(words(e.hw_config(), 3));
  let action = null;
  if (state !== null) {
    words(e.hw_state(), state.length).set(state);
    action = Array.from(words(e.hw_step(), 3));
  }
  JSON.stringify({attributes, action});
`);
const results = requests.map(request => {
  try {
    return JSON.parse(script.runInNewContext({
      bytes: Buffer.from(request.wasm, 'base64'), state: request.state
    }, {timeout: 50}));
  } catch (error) {
    return {error: String(error.message).slice(0, 160)};
  }
});
process.stdout.write(JSON.stringify(results));
