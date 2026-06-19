/**
 * Client-side JavaScript execution in a sandboxed Web Worker (free, native).
 *
 * Why a Worker: user code runs off the main thread, so an infinite loop can be
 * terminated with worker.terminate() without freezing the UI, and the user's
 * code has no access to the page DOM, cookies, or app globals.
 *
 * Like the Python runner, this is for the Run button and VISIBLE tests only —
 * the authoritative verdict (with hidden tests) is computed on the backend.
 */

// The worker program, embedded as a string and instantiated from a Blob URL so
// we need no extra bundler/worker-file configuration.
const WORKER_SRC = `
self.onmessage = (e) => {
  const { source, tests } = e.data || {};
  const assert = (c, m) => { if (!c) throw new Error(m || 'assertion failed'); };
  const logs = [];
  const realLog = (...a) => logs.push(a.map(x => {
    try { return typeof x === 'string' ? x : JSON.stringify(x); } catch { return String(x); }
  }).join(' '));
  self.console = { log: realLog, info: realLog, warn: realLog, error: realLog };

  let compileError = null;
  try { new Function('assert', source); }
  catch (err) { compileError = String(err && err.stack ? err.stack : err); }

  const results = [];
  for (const t of (tests || [])) {
    if (compileError !== null) {
      results.push({ name: t.name, passed: false, message: 'solution failed to load' });
      continue;
    }
    try {
      const fn = new Function('assert', 'console', source + '\\n;(function(){\\n' + t.code + '\\n})();');
      fn(assert, self.console);
      results.push({ name: t.name, passed: true, message: '' });
    } catch (err) {
      results.push({ name: t.name, passed: false, message: String(err && err.message ? err.message : err) });
    }
  }
  self.postMessage({ compileError, results, stdout: logs.join('\\n') });
};
`

function makeWorker() {
  const blob = new Blob([WORKER_SRC], { type: 'application/javascript' })
  const url = URL.createObjectURL(blob)
  const worker = new Worker(url)
  // Revoke once constructed; the worker keeps running.
  URL.revokeObjectURL(url)
  return worker
}

/**
 * Run user JS + tests in a worker with a hard timeout. Each test is {name, code}
 * and passes if it runs without throwing. Returns
 * { ok, results:[{name,passed,message}], stdout, error, timedOut }.
 */
export function runJavaScriptTests(source, tests, { timeoutMs = 8000 } = {}) {
  return new Promise((resolve) => {
    let worker
    try {
      worker = makeWorker()
    } catch (err) {
      resolve({ ok: false, results: [], stdout: '', error: 'Web Worker unavailable in this browser.', timedOut: false })
      return
    }

    const timer = setTimeout(() => {
      try { worker.terminate() } catch { /* ignore */ }
      resolve({
        ok: false, results: [], stdout: '', timedOut: true,
        error: `Execution timed out after ${Math.round(timeoutMs / 1000)}s (possible infinite loop).`,
      })
    }, timeoutMs)

    worker.onmessage = (e) => {
      clearTimeout(timer)
      try { worker.terminate() } catch { /* ignore */ }
      const { compileError, results, stdout } = e.data || {}
      resolve({
        ok: !compileError,
        results: results || [],
        stdout: stdout || '',
        error: compileError || '',
        timedOut: false,
      })
    }

    worker.onerror = (err) => {
      clearTimeout(timer)
      try { worker.terminate() } catch { /* ignore */ }
      resolve({ ok: false, results: [], stdout: '', error: String(err.message || 'Worker error'), timedOut: false })
    }

    worker.postMessage({
      source,
      tests: (tests || []).map((t, i) => ({ name: t.name || `test_${i}`, code: t.code || '' })),
    })
  })
}

/** Run plain JS (no tests) for the Run button, capturing console output. */
export function runJavaScript(source, opts = {}) {
  return runJavaScriptTests(source, [], opts).then((r) => ({
    ok: r.ok,
    stdout: r.stdout,
    error: r.error,
    timedOut: r.timedOut,
  }))
}
